#!/bin/sh
/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -hide_banner -y -nostdin -loop 1 -framerate 30 -t 8.000 -i /Users/abishaikc/Phalanx-Solution/video/tools/assembly/assets/ui_mock.png -ss 0.000 -t 9.200 -i /Users/abishaikc/Phalanx-Solution/video/tools/assembly/assets/WeibullCurves.mp4 -ss 0.000 -t 6.400 -i /Users/abishaikc/Phalanx-Solution/video/tools/assembly/assets/BayesEquation_alpha_qtrle.mov -i /Users/abishaikc/Phalanx-Solution/video/tools/assembly/assets/narration.wav -stream_loop -1 -i /Users/abishaikc/Phalanx-Solution/video/tools/assembly/assets/music_bed.wav -filter_complex '[0:v]scale=3840:2160:force_original_aspect_ratio=decrease,pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=white,zoompan=z='"'"'1.0+(1.08-1.0)*on/239'"'"':x='"'"'0.35*(iw-iw/zoom)'"'"':y='"'"'0.45*(ih-ih/zoom)'"'"':d=1:s=1920x1080:fps=30,fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v0];
[1:v]fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[v1];
[v0][v1]xfade=transition=fade:duration=0.6:offset=7.400[x1];
[2:v]fps=30,format=yuva444p,setpts=PTS-STARTPTS,scale=iw*0.5:-2,fade=t=in:st=0:d=0.2:alpha=1,fade=t=out:st=5.900:d=0.5:alpha=1,tpad=start_duration=0.800:color=black@0.0[o0];
[x1][o0]overlay=x='"'"'W-w-40'"'"':y='"'"'H-h-150'"'"':eof_action=pass:format=auto[ov0];
[ov0]subtitles=filename='"'"'/Users/abishaikc/Phalanx-Solution/video/tools/assembly/out/smoke_ffmpeg_sidechain.captions.ass'"'"',format=yuv420p[vout];
[3:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=0dB,adelay=1000:all=1[n0];
[n0]apad,atrim=0:16.600[nar];
[4:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:16.600,volume=-4dB,afade=t=in:st=0:d=1.0,afade=t=out:st=14.600:d=2.0[mus];
[nar]asplit=2[nar_mix][nar_sc];
[mus][nar_sc]sidechaincompress=threshold=0.015:ratio=10:attack=30:release=500:makeup=1[mus_d];
[mus_d]asplit=2[mus_mix][mus_dbg];
[nar_mix][mus_mix]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:16.600[aout]' -map '[vout]' -map '[aout]' -t 16.600 -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -ar 48000 -movflags +faststart /Users/abishaikc/Phalanx-Solution/video/tools/assembly/out/smoke_ffmpeg_sidechain.mp4 -map '[mus_dbg]' -t 16.600 -c:a pcm_s16le /Users/abishaikc/Phalanx-Solution/video/tools/assembly/out/smoke_ffmpeg_sidechain.ducked_music.wav
