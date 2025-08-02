package bme

import (
	"unsafe"

	"github.com/ebitengine/purego"
)

type cddevice_t unsafe.Pointer
type cdda_t unsafe.Pointer
type paranoia_t unsafe.Pointer
type lsn_t int // 32

type track_t uint8
type cdtext_t unsafe.Pointer
type driver_return_code_t int8 // 0 is success, negative values are error
type cdtext_field_t uint8
type paranoia_mode_t uint8

var cdio_open func(string, unsafe.Pointer) cddevice_t
var cdio_get_default_device func(cddevice_t) string
var cdio_get_first_track_num func(cddevice_t) track_t
var cdio_get_num_tracks func(cddevice_t) track_t
var cdio_get_cdtext func(cddevice_t) cdtext_t
var cdtext_get func(cdtext_t, cdtext_field_t, track_t) string
var mmc_get_mcn func(cddevice_t) string
var mmc_get_track_isrc func(cddevice_t, track_t) string
var cdio_destroy func(cddevice_t)
var cdtext_destroy func(cdtext_t)
var cdio_get_track_lba func(cddevice_t, track_t) int
var mmc_eject_media func(cddevice_t) int
var mmc_test_unit_ready func(cddevice_t, uint32) driver_return_code_t // uint32 is timeout in ms
var cdio_cddap_open func(cdda_t) driver_return_code_t
var cdio_cddap_disc_firstsector func(cdda_t) lsn_t
var cdio_cddap_identify_cdio func(cddevice_t, int, unsafe.Pointer) cdda_t
var cdio_cddap_messages func(cdda_t) string
var cdio_cddap_errors func(cdda_t) string
var cdio_cddap_close_no_free_cdio func(cdda_t) bool
var cdio_cddap_verbose_set func(cdda_t, int, int)
var cdio_cddap_track_firstsector func(cdda_t, track_t) lsn_t
var cdio_cddap_track_lastsector func(cdda_t, track_t) lsn_t
var cdio_paranoia_init func(cdda_t) paranoia_t
var cdio_paranoia_modeset func(paranoia_t, paranoia_mode_t)
var cdio_paranoia_seek func(paranoia_t, lsn_t, int) lsn_t
var cdio_paranoia_read func(paranoia_t, unsafe.Pointer) *byte // *[CDIO_CD_FRAMESIZE_RAW]byte
var cdio_paranoia_free func(paranoia_t)
var cdio_get_media_changed func(cddevice_t) bool
var mmc_get_tray_status func(cddevice_t) bool

type mb5_release_list unsafe.Pointer
type mb5_release unsafe.Pointer
type mb5_query unsafe.Pointer
type mb5_metadata unsafe.Pointer
type mb5_discid string
type mb5_tQueryResult int // enum eQuery_Success=0, >0 == err
type mb5_disc unsafe.Pointer
type mb5_artist_credit unsafe.Pointer
type mb5_media_list unsafe.Pointer
type mb5_medium unsafe.Pointer
type mb5_track_list unsafe.Pointer
type mb5_track unsafe.Pointer
type mb5_recording unsafe.Pointer
type mb5_namecreditlist unsafe.Pointer
type mb5_namecredit unsafe.Pointer

var mb5_query_new func(string, string, int) mb5_query // "cdlookupcexample-1.0",NULL,0
var mb5_query_lookup_discid func(mb5_query, mb5_discid) mb5_release_list
var mb5_release_list_size func(mb5_release_list) int
var mb5_release_list_item func(mb5_release_list, int) mb5_release
var mb5_release_get_id func(mb5_release, unsafe.Pointer, int) // fetched mb5_release, fills []byte of size int
var mb5_query_query func(mb5_query, string, string, string, int, unsafe.Pointer, unsafe.Pointer) mb5_metadata
var mb5_metadata_get_release func(mb5_metadata) mb5_release
var mb5_query_get_lasterrormessage func(mb5_query, *byte, int) // fills []byte of size int
var mb5_query_get_lastresult func(mb5_query) mb5_tQueryResult
var mb5_metadata_get_disc func(mb5_metadata) mb5_disc
var mb5_disc_get_releaselist func(mb5_disc) mb5_release_list
var mb5_release_get_title func(mb5_release, unsafe.Pointer, int)
var mb5_release_get_artistcredit func(mb5_release) mb5_artist_credit
var mb5_metadata_delete func(mb5_metadata)
var mb5_release_media_matching_discid func(mb5_release, string) mb5_media_list
var mb5_medium_get_tracklist func(mb5_medium) mb5_track_list
var mb5_medium_list_item func(mb5_media_list, int) mb5_medium
var mb5_medium_list_size func(mb5_media_list) int
var mb5_medium_get_position func(mb5_medium) int
var mb5_disc_clone func(mb5_disc) mb5_disc
var mb5_disc_delete func(mb5_disc)
var mb5_release_list_clone func(mb5_release_list) mb5_release_list
var mb5_release_list_delete func(mb5_release_list)
var mb5_release_clone func(mb5_release) mb5_release
var mb5_release_delete func(mb5_release)
var mb5_medium_list_get_trackcount func(mb5_media_list) int
var mb5_metadata_clone func(mb5_metadata) mb5_metadata
var mb5_release_get_mediumlist func(mb5_release) mb5_media_list
var mb5_track_list_clone func(mb5_track_list) mb5_track_list
var mb5_track_list_delete func(mb5_track_list)
var mb5_track_list_item func(mb5_track_list, int) mb5_track
var mb5_track_get_title func(mb5_track, *byte, int)
var mb5_track_get_artistcredit func(mb5_track) mb5_artist_credit
var mb5_track_get_recording func(mb5_track) mb5_recording
var mb5_recording_get_id func(mb5_recording, *byte, int)
var mb5_artistcredit_get_namecreditlist func(mb5_artist_credit) mb5_namecreditlist
var mb5_namecredit_list_get_count func(mb5_namecreditlist) int
var mb5_namecredit_list_item func(mb5_namecreditlist, int) mb5_namecredit
var mb5_namecredit_get_name func(mb5_namecredit, *byte, int)
var mb5_namecredit_get_joinphrase func(mb5_namecredit, *byte, int)
var mb5_track_list_get_count func(mb5_track_list) int
var mb5_track_get_position func(mb5_track) int
var mb5_recording_get_title func(mb5_recording, *byte, int)

const CDIO_CDROM_LEADOUT_TRACK track_t = 0xAA
const CDDA_MESSAGE_FORGETIT int = 0
const CDDA_MESSAGE_PRINTIT int = 1
const CDDA_MESSAGE_LOGIT int = 2
const CDIO_CD_FRAMESIZE_RAW int = 2352
const PARANOIA_MODE_FULL paranoia_mode_t = paranoia_mode_t(0xff)
const PARANOIA_MODE_NEVERSKIP paranoia_mode_t = paranoia_mode_t(0x20)
const SEEK_SET int = 0 // libc

func loadlibs() {
	libcdio, err := purego.Dlopen("libcdio.so", purego.RTLD_NOW|purego.RTLD_GLOBAL)
	if err != nil {
		panic(err)
	}

	libcdio_cdda, err := purego.Dlopen("libcdio_cdda.so", purego.RTLD_NOW|purego.RTLD_GLOBAL)
	if err != nil {
		panic(err)
	}

	libcdio_paranoia, err := purego.Dlopen("libcdio_paranoia.so", purego.RTLD_NOW|purego.RTLD_GLOBAL)
	if err != nil {
		panic(err)
	}

	libmusicbrainz5, err := purego.Dlopen("libmusicbrainz5.so", purego.RTLD_NOW|purego.RTLD_GLOBAL)
	if err != nil {
		panic(err)
	}

	purego.RegisterLibFunc(&cdio_open, libcdio, "cdio_open")
	purego.RegisterLibFunc(&cdio_get_default_device, libcdio, "cdio_get_default_device")
	purego.RegisterLibFunc(&cdio_get_first_track_num, libcdio, "cdio_get_first_track_num")
	purego.RegisterLibFunc(&cdio_get_num_tracks, libcdio, "cdio_get_num_tracks")
	purego.RegisterLibFunc(&cdio_get_cdtext, libcdio, "cdio_get_cdtext")
	purego.RegisterLibFunc(&cdtext_get, libcdio, "cdtext_get")
	purego.RegisterLibFunc(&mmc_get_mcn, libcdio, "mmc_get_mcn")
	purego.RegisterLibFunc(&mmc_get_track_isrc, libcdio, "mmc_get_track_isrc")
	purego.RegisterLibFunc(&cdio_destroy, libcdio, "cdio_destroy")
	purego.RegisterLibFunc(&cdio_get_track_lba, libcdio, "cdio_get_track_lba")
	purego.RegisterLibFunc(&mmc_eject_media, libcdio, "mmc_eject_media")
	purego.RegisterLibFunc(&mmc_test_unit_ready, libcdio, "mmc_test_unit_ready")
	purego.RegisterLibFunc(&cdio_get_media_changed, libcdio, "cdio_get_media_changed")
	purego.RegisterLibFunc(&mmc_get_tray_status, libcdio, "mmc_get_tray_status")

	purego.RegisterLibFunc(&cdio_cddap_open, libcdio_cdda, "cdio_cddap_open")
	purego.RegisterLibFunc(&cdio_cddap_disc_firstsector, libcdio_cdda, "cdio_cddap_disc_firstsector")
	purego.RegisterLibFunc(&cdio_cddap_identify_cdio, libcdio_cdda, "cdio_cddap_identify_cdio")
	purego.RegisterLibFunc(&cdio_cddap_messages, libcdio_cdda, "cdio_cddap_messages")
	purego.RegisterLibFunc(&cdio_cddap_errors, libcdio_cdda, "cdio_cddap_errors")
	purego.RegisterLibFunc(&cdio_cddap_close_no_free_cdio, libcdio_cdda, "cdio_cddap_close_no_free_cdio")
	purego.RegisterLibFunc(&cdio_cddap_verbose_set, libcdio_cdda, "cdio_cddap_verbose_set")
	purego.RegisterLibFunc(&cdio_cddap_track_firstsector, libcdio_cdda, "cdio_cddap_track_firstsector")
	purego.RegisterLibFunc(&cdio_cddap_track_lastsector, libcdio_cdda, "cdio_cddap_track_lastsector")

	purego.RegisterLibFunc(&cdio_paranoia_init, libcdio_paranoia, "cdio_paranoia_init")
	purego.RegisterLibFunc(&cdio_paranoia_modeset, libcdio_paranoia, "cdio_paranoia_modeset")
	purego.RegisterLibFunc(&cdio_paranoia_seek, libcdio_paranoia, "cdio_paranoia_seek")
	purego.RegisterLibFunc(&cdio_paranoia_read, libcdio_paranoia, "cdio_paranoia_read")
	purego.RegisterLibFunc(&cdio_paranoia_free, libcdio_paranoia, "cdio_paranoia_free")

	purego.RegisterLibFunc(&mb5_query_new, libmusicbrainz5, "mb5_query_new")
	purego.RegisterLibFunc(&mb5_query_lookup_discid, libmusicbrainz5, "mb5_query_lookup_discid")
	purego.RegisterLibFunc(&mb5_release_list_size, libmusicbrainz5, "mb5_release_list_size")
	purego.RegisterLibFunc(&mb5_release_list_item, libmusicbrainz5, "mb5_release_list_item")
	purego.RegisterLibFunc(&mb5_release_get_id, libmusicbrainz5, "mb5_release_get_id")
	purego.RegisterLibFunc(&mb5_query_query, libmusicbrainz5, "mb5_query_query")
	purego.RegisterLibFunc(&mb5_metadata_get_release, libmusicbrainz5, "mb5_metadata_get_release")
	purego.RegisterLibFunc(&mb5_query_get_lasterrormessage, libmusicbrainz5, "mb5_query_get_lasterrormessage")
	purego.RegisterLibFunc(&mb5_query_get_lastresult, libmusicbrainz5, "mb5_query_get_lastresult")
	purego.RegisterLibFunc(&mb5_metadata_get_disc, libmusicbrainz5, "mb5_metadata_get_disc")
	purego.RegisterLibFunc(&mb5_disc_get_releaselist, libmusicbrainz5, "mb5_disc_get_releaselist")
	purego.RegisterLibFunc(&mb5_release_get_title, libmusicbrainz5, "mb5_release_get_title")
	purego.RegisterLibFunc(&mb5_release_get_artistcredit, libmusicbrainz5, "mb5_release_get_artistcredit")
	purego.RegisterLibFunc(&mb5_release_media_matching_discid, libmusicbrainz5, "mb5_release_media_matching_discid")
	purego.RegisterLibFunc(&mb5_medium_get_tracklist, libmusicbrainz5, "mb5_medium_get_tracklist")
	purego.RegisterLibFunc(&mb5_medium_list_item, libmusicbrainz5, "mb5_medium_list_item")
	purego.RegisterLibFunc(&mb5_medium_list_size, libmusicbrainz5, "mb5_medium_list_size")
	purego.RegisterLibFunc(&mb5_medium_get_position, libmusicbrainz5, "mb5_medium_get_position")
	purego.RegisterLibFunc(&mb5_disc_clone, libmusicbrainz5, "mb5_disc_clone")
	purego.RegisterLibFunc(&mb5_disc_delete, libmusicbrainz5, "mb5_disc_delete")
	purego.RegisterLibFunc(&mb5_release_list_clone, libmusicbrainz5, "mb5_release_list_clone")
	purego.RegisterLibFunc(&mb5_release_list_delete, libmusicbrainz5, "mb5_release_list_delete")
	purego.RegisterLibFunc(&mb5_release_clone, libmusicbrainz5, "mb5_release_clone")
	purego.RegisterLibFunc(&mb5_release_delete, libmusicbrainz5, "mb5_release_delete")
	purego.RegisterLibFunc(&mb5_medium_list_get_trackcount, libmusicbrainz5, "mb5_medium_list_get_trackcount")
	purego.RegisterLibFunc(&mb5_metadata_clone, libmusicbrainz5, "mb5_metadata_clone")
	purego.RegisterLibFunc(&mb5_metadata_delete, libmusicbrainz5, "mb5_metadata_delete")
	purego.RegisterLibFunc(&mb5_release_get_mediumlist, libmusicbrainz5, "mb5_release_get_mediumlist")
	purego.RegisterLibFunc(&mb5_track_list_clone, libmusicbrainz5, "mb5_track_list_clone")
	purego.RegisterLibFunc(&mb5_track_list_delete, libmusicbrainz5, "mb5_track_list_delete")
	purego.RegisterLibFunc(&mb5_track_list_item, libmusicbrainz5, "mb5_track_list_item")
	purego.RegisterLibFunc(&mb5_track_get_title, libmusicbrainz5, "mb5_track_get_title")
	purego.RegisterLibFunc(&mb5_track_get_artistcredit, libmusicbrainz5, "mb5_track_get_artistcredit")
	purego.RegisterLibFunc(&mb5_track_get_recording, libmusicbrainz5, "mb5_track_get_recording")
	purego.RegisterLibFunc(&mb5_recording_get_id, libmusicbrainz5, "mb5_recording_get_id")
	purego.RegisterLibFunc(&mb5_artistcredit_get_namecreditlist, libmusicbrainz5, "mb5_artistcredit_get_namecreditlist")
	purego.RegisterLibFunc(&mb5_namecredit_list_get_count, libmusicbrainz5, "mb5_namecredit_list_get_count")
	purego.RegisterLibFunc(&mb5_namecredit_list_item, libmusicbrainz5, "mb5_namecredit_list_item")
	purego.RegisterLibFunc(&mb5_namecredit_get_name, libmusicbrainz5, "mb5_namecredit_get_name")
	purego.RegisterLibFunc(&mb5_namecredit_get_joinphrase, libmusicbrainz5, "mb5_namecredit_get_joinphrase")
	purego.RegisterLibFunc(&mb5_track_list_get_count, libmusicbrainz5, "mb5_track_list_get_count")
	purego.RegisterLibFunc(&mb5_track_get_position, libmusicbrainz5, "mb5_track_get_position")
	purego.RegisterLibFunc(&mb5_recording_get_title, libmusicbrainz5, "mb5_recording_get_title")
}
