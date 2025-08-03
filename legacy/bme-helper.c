/*
 * Scot C. Bontrager (scot@indievisible.org) May 15, 2011 - This file is
 * public domain
 * 
 * requires libcdio (tested with 0.83git from date of writing)
 *
 * gcc -O2 -I /usr/local/include -o bme-helper bme-helper.c -R /usr/local/lib -L /usr/local/lib -lcdio -lcrypto -lcdio_cdda -lcdda_interface
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <cdio/cdio.h>
#include <cdio/cdtext.h>
#include <cdio/mmc.h>
#include <cdio/cdda.h>
#include <openssl/sha.h>
#include <string.h>

char           *bme_get_track_isrc(const CdIo_t *, const track_t);
char           *get_mbdiscid(const CdIo_t *);
char           *bme_get_toc(const CdIo_t *, cdrom_drive_t *);
unsigned char  *rfc822_binary(void *, unsigned long, unsigned long *);

int 
main(int argc, const char *argv[])
{
	track_t         first_track, tracks, i;
	CdIo_t         *cdio;
	cdrom_drive_t  *cdrom;
	cdtext_t       *cdtext;
	cdtext_field_t  j;
	char           *mcn;
	int 		messagedest = 0;
	char 		**ppsz_messages;

	cdio = cdio_open(NULL, DRIVER_DEVICE);
	if (cdio == NULL) {
	    printf("Couldn't find CD\n");
	    return 1;
	}

/*	idmessage(messagedest, ppsz_messages, "setting CDDA mode"); */
	cdrom = cdio_cddap_identify_cdio(cdio, messagedest, ppsz_messages);

	first_track = cdio_get_first_track_num(cdio);
	tracks = cdio_get_num_tracks(cdio);

	for (i = 0; i <= tracks; i++) {
		cdtext = cdio_get_cdtext(cdio, i);
		if (cdtext != NULL) {
			for (j = 0; j < MAX_CDTEXT_FIELDS; j++) {
				if (cdtext->field[j] != NULL) {
					printf("%s_%02d=\"%s\"\n", cdtext_field2str(j), i, cdtext->field[j] ? cdtext->field[j] : "");
				}
			}
		}
		mcn = bme_get_track_isrc(cdio, i);
		if (mcn != NULL) {
			printf("Q_ISRC_%02d=%s\n", i, mcn);
			free(mcn);
		}
	}

	mcn = mmc_get_mcn(cdio);
	if (mcn != NULL && strncmp("000000000000", mcn, 12)) {
		printf("MCN=\"%s\"\n", mcn);
		free(mcn);
	}
	mcn = get_mbdiscid(cdio);
	if (mcn != NULL) {
		printf("MUSICBRAINZ_DISCID=\"%s\"\n", mcn);
		free(mcn);
	}
	bme_get_toc(cdio, cdrom);
	cdio_destroy(cdio);

	return 0;
}

char           *
bme_get_track_isrc(const CdIo_t * cdio, const track_t track)
{
	mmc_cdb_t       cdb = {{0,}};
	char            buf[28] = {0,};
	int             status;

	CDIO_MMC_SET_COMMAND(cdb.field, CDIO_MMC_GPCMD_READ_SUBCHANNEL);
	CDIO_MMC_SET_READ_LENGTH8(cdb.field, sizeof(buf));

	cdb.field[1] = 0x0;
	cdb.field[2] = 1 << 6;
	cdb.field[3] = CDIO_SUBCHANNEL_TRACK_ISRC;	/* 0x03 */
	cdb.field[6] = track;

	status = mmc_run_cmd(cdio, mmc_timeout_ms, &cdb, SCSI_MMC_DATA_READ,
			     sizeof(buf), buf);
	if (status == 0 && strncmp("000000000000", &buf[9], 12)) {
		return strdup(&buf[9]);
	}
	return NULL;
}

char           *
get_mbdiscid(const CdIo_t * cdio)
{
	SHA_CTX         sha;
	unsigned char   digest[20], *base64;
	unsigned long   size;
	char            tmp[17];/* for 8 hex digits (16 to avoid trouble) */
	int             first_track, tracks, leadout, lba, i;

	SHA1_Init(&sha);

	first_track = cdio_get_first_track_num(cdio);
	sprintf(tmp, "%02X", first_track);
	SHA1_Update(&sha, (unsigned char *) tmp, strlen(tmp));

	tracks = cdio_get_num_tracks(cdio);
	sprintf(tmp, "%02X", tracks);
	SHA1_Update(&sha, (unsigned char *) tmp, strlen(tmp));

	leadout = cdio_get_track_lba(cdio, CDIO_CDROM_LEADOUT_TRACK);
	sprintf(tmp, "%08X", leadout);
	SHA1_Update(&sha, (unsigned char *) tmp, strlen(tmp));

	for (i = 1; i < 100; i++) {
		if (i <= tracks) {
			lba = cdio_get_track_lba(cdio, i);
		} else {
			lba = 0;
		}

		sprintf(tmp, "%08X", lba);
		SHA1_Update(&sha, (unsigned char *) tmp, strlen(tmp));
	}

	SHA1_Final(digest, &sha);

	base64 = rfc822_binary(digest, sizeof(digest), &size);
	return (base64);
}

char           *
bme_get_toc(const CdIo_t * cdio, cdrom_drive_t * cdrom)
{
	int             first_track, tracks, leadout, lba, i;

	first_track = cdio_get_first_track_num(cdio);
	printf("TOC=\"%d", first_track);

/*	tracks = cdio_get_num_tracks(cdio); */
/*	tracks = cdio_cddap_tracks(cdrom); */

	for (i = first_track, tracks = 0; i <= cdio_get_num_tracks(cdio); i++) {
		if (cdio_cddap_track_audiop(cdrom, i)) tracks++; 
	}
	printf(" %d", tracks);

	leadout = cdio_get_track_lba(cdio, CDIO_CDROM_LEADOUT_TRACK);
	printf(" %d", leadout);

	for (i = 1; i <= tracks; i++) {
		if (cdio_cddap_track_audiop(cdrom, i)) { 
	    	    lba = cdio_get_track_lba(cdio, i);
		    printf(" %d", lba);
		}
	}
	printf("\"\n");

	printf("TRACKS=\"");
	tracks = cdio_cddap_tracks(cdrom);

	for (i = first_track; i <= cdio_get_num_tracks(cdio); i++) {
		if (cdio_cddap_track_audiop(cdrom, i)) { 
		    printf("%d ", i);
		}
	}
	printf("\"\n");
}

unsigned char  *
rfc822_binary(void *src, unsigned long srcl, unsigned long *len)
{
	unsigned char  *ret, *d;
	unsigned char  *s = (unsigned char *) src;
	char           *v = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._";
	unsigned long   i = ((srcl + 2) / 3) * 4;
	*len = i += 2 * ((i / 60) + 1);
	d = ret = (unsigned char *) malloc((size_t)++ i);
	for (i = 0; srcl; s += 3) {	/* process tuplets */
		*d++ = v[s[0] >> 2];	/* byte 1: high 6 bits (1) */
		/* byte 2: low 2 bits (1), high 4 bits (2) */
		*d++ = v[((s[0] << 4) + (--srcl ? (s[1] >> 4) : 0)) & 0x3f];
		/* byte 3: low 4 bits (2), high 2 bits (3) */
		*d++ = srcl ? v[((s[1] << 2) + (--srcl ? (s[2] >> 6) : 0)) & 0x3f] : '-';
		/* byte 4: low 6 bits (3) */
		*d++ = srcl ? v[s[2] & 0x3f] : '-';
		if (srcl)
			srcl--;	/* count third character if processed */
		if ((++i) == 15) {	/* output 60 characters? */
			i = 0;	/* restart line break count, insert CRLF */
			*d++ = '\015';
			*d++ = '\012';
		}
	}
	*d = '\0';		/* tie off string */

	return ret;		/* return the resulting string */
}
