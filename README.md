# go-bme
Tool to rip CDs and encode to ALAC in bulk

I've written this three times over the past 20 years. First in sh, then in python2, now in Go. First it did mp3, then flac, now ALAC. It's been 14 years since the last time I ripped a mess of CDs in bulk and yet I keep buying them... so it's time to rip more. The old Python2 tool had rotted to the point of being more work to update than it was worth. So, time to rewrite it.

I'm using purego to wrap libcdio (because I know that code) and libmusicbrainz5 (because I love MusicBrainz and none of the exiting go libraries would do what I needed).

This is for me; if it doesn't do what you want/need, either find another tool or modify the code to suit your needs.

It's a batch system, designed to keep the system as busy as possible while working. Just keep feeding it CDs and eventually the final result will pop out in the "done" directory.

If the discID is in MusicBrainz, it will be great. If the cd has cd-text you should be fine. If neither is true, well, use MusicBrainz Picard and contrbute the discID to MB and try again.
