from __future__ import annotations

import subprocess
import asyncio
import shlex
import json
import re
import io

from typing import Any, Callable

from discord import FFmpegAudio
from discord.oggparse import OggStream


class FFmpegOpusAudio(FFmpegAudio):
    """An audio source from FFmpeg (or AVConv).

    This launches a sub-process to a specific input file given.  However, rather than
    producing PCM packets like :class:`FFmpegPCMAudio` does that need to be encoded to
    Opus, this class produces Opus packets, skipping the encoding step done by the library.

    Alternatively, instead of instantiating this class directly, you can use
    :meth:`FFmpegOpusAudio.from_probe` to probe for bitrate and codec information.  This
    can be used to opportunistically skip pointless re-encoding of existing Opus audio data
    for a boost in performance at the cost of a short initial delay to gather the information.
    The same can be achieved by passing ``copy`` to the ``codec`` parameter, but only if you
    know that the input source is Opus encoded beforehand.

    .. versionadded:: 1.3

    .. warning::

        You must have the ffmpeg or avconv executable in your path environment
        variable in order for this to work.

    Parameters
    ----------
    source: Union[:class:`str`, :class:`io.BufferedIOBase`]
        The input that ffmpeg will take and convert to Opus bytes.
        If ``pipe`` is ``True`` then this is a file-like object that is
        passed to the stdin of ffmpeg.
    bitrate: :class:`int`
        The bitrate in kbps to encode the output to.  Defaults to ``128``.
    codec: Optional[:class:`str`]
        The codec to use to encode the audio data.  Normally this would be
        just ``libopus``, but is used by :meth:`FFmpegOpusAudio.from_probe` to
        opportunistically skip pointlessly re-encoding Opus audio data by passing
        ``copy`` as the codec value.  Any values other than ``copy``, ``opus``, or
        ``libopus`` will be considered ``libopus``.  Defaults to ``libopus``.

        .. warning::

            Do not provide this parameter unless you are certain that the audio input is
            already Opus encoded.  For typical use :meth:`FFmpegOpusAudio.from_probe`
            should be used to determine the proper value for this parameter.

    executable: :class:`str`
        The executable name (and path) to use. Defaults to ``ffmpeg``.
    pipe: :class:`bool`
        If ``True``, denotes that ``source`` parameter will be passed
        to the stdin of ffmpeg. Defaults to ``False``.
    stderr: Optional[:term:`py:file object`]
        A file-like object to pass to the Popen constructor.
        Could also be an instance of ``subprocess.PIPE``.
    before_options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg before the ``-i`` flag.
    options: Optional[:class:`str`]
        Extra command line arguments to pass to ffmpeg after the ``-i`` flag.

    Raises
    ------
    ClientException
        The subprocess failed to be created.
    """

    def __init__(
        self,
        source: str | io.BufferedIOBase,
        *,
        bitrate: int = 128,
        codec: str | None = None,
        executable: str = "ffmpeg",
        pipe=False,
        stderr=None,
        before_options=None,
        options=None,
    ) -> None:
        args = []
        subprocess_kwargs = {
            "stdin": subprocess.PIPE if pipe else subprocess.DEVNULL,
            "stderr": stderr,
        }

        if isinstance(before_options, str):
            args.extend(shlex.split(before_options))

        args.append("-i")
        args.append("-" if pipe else source)

        codec = "copy" if codec == "copy" else "libopus"

        args.extend(
            (
                "-map_metadata",
                "-1",
                "-f",
                "opus",
                "-c:a",
                codec,
                "-loglevel",
                "warning",
            )
        )

        if codec != "copy":
            args.extend(
                (
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-b:a",
                    f"{bitrate}k",
                )
            )

        if isinstance(options, str):
            args.extend(shlex.split(options))

        args.append("pipe:1")

        super().__init__(source, executable=executable, args=args, **subprocess_kwargs)
        self._packet_iter = OggStream(self._stdout).iter_packets()

    @classmethod
    async def from_probe(
        cls: type[FT],
        source: str,
        *,
        method: str | Callable[[str, str], tuple[str | None, int | None]] | None = None,
        **kwargs: Any,
    ) -> FT:
        """|coro|

        A factory method that creates a :class:`FFmpegOpusAudio` after probing
        the input source for audio codec and bitrate information.

        Parameters
        ----------
        source
            Identical to the ``source`` parameter for the constructor.
        method: Optional[Union[:class:`str`, Callable[:class:`str`, :class:`str`]]]
            The probing method used to determine bitrate and codec information. As a string, valid
            values are ``native`` to use ffprobe (or avprobe) and ``fallback`` to use ffmpeg
            (or avconv).  As a callable, it must take two string arguments, ``source`` and
            ``executable``.  Both parameters are the same values passed to this factory function.
            ``executable`` will default to ``ffmpeg`` if not provided as a keyword argument.
        kwargs
            The remaining parameters to be passed to the :class:`FFmpegOpusAudio` constructor,
            excluding ``bitrate`` and ``codec``.

        Returns
        -------
        :class:`FFmpegOpusAudio`
            An instance of this class.

        Raises
        ------
        AttributeError
            Invalid probe method, must be ``'native'`` or ``'fallback'``.
        TypeError
            Invalid value for ``probe`` parameter, must be :class:`str` or a callable.

        Examples
        --------

        Use this function to create an :class:`FFmpegOpusAudio` instance instead of the constructor: ::

            source = await discord.FFmpegOpusAudio.from_probe("song.webm")
            voice_client.play(source)

        If you are on Windows and don't have ffprobe installed, use the ``fallback`` method
        to probe using ffmpeg instead: ::

            source = await discord.FFmpegOpusAudio.from_probe("song.webm", method='fallback')
            voice_client.play(source)

        Using a custom method of determining codec and bitrate: ::

            def custom_probe(source, executable):
                # some analysis code here
                return codec, bitrate

            source = await discord.FFmpegOpusAudio.from_probe("song.webm", method=custom_probe)
            voice_client.play(source)
        """

        executable = kwargs.get("executable")
        codec, bitrate = await cls.probe(source, method=method, executable=executable)
        codec = "copy" if codec in ("opus", "libopus") else "libopus"
        return cls(source, bitrate=bitrate, codec=codec, **kwargs)  # type: ignore

    @classmethod
    async def probe(
        cls,
        source: str,
        *,
        method: str | Callable[[str, str], tuple[str | None, int | None]] | None = None,
        executable: str | None = None,
    ) -> tuple[str | None, int | None]:
        """|coro|

        Probes the input source for bitrate and codec information.

        Parameters
        ----------
        source
            Identical to the ``source`` parameter for :class:`FFmpegOpusAudio`.
        method
            Identical to the ``method`` parameter for :meth:`FFmpegOpusAudio.from_probe`.
        executable: :class:`str`
            Identical to the ``executable`` parameter for :class:`FFmpegOpusAudio`.

        Returns
        -------
        Optional[Tuple[Optional[:class:`str`], Optional[:class:`int`]]]
            A 2-tuple with the codec and bitrate of the input source.

        Raises
        ------
        AttributeError
            Invalid probe method, must be ``'native'`` or ``'fallback'``.
        TypeError
            Invalid value for ``probe`` parameter, must be :class:`str` or a callable.
        """

        method = method or "native"
        executable = executable or "ffmpeg"
        probefunc = fallback = None

        if isinstance(method, str):
            probefunc = getattr(cls, f"_probe_codec_{method}", None)
            if probefunc is None:
                raise AttributeError(f"Invalid probe method {method!r}")

            if probefunc is cls._probe_codec_native:
                fallback = cls._probe_codec_fallback

        elif callable(method):
            probefunc = method
            fallback = cls._probe_codec_fallback
        else:
            raise TypeError(
                "Expected str or callable for parameter 'probe', "
                f"not '{method.__class__.__name__}'"
            )

        codec = bitrate = None
        loop = asyncio.get_event_loop()
        try:
            codec, bitrate = await loop.run_in_executor(None, lambda: probefunc(source, executable))  # type: ignore
        except Exception:
            if not fallback:
                _log.exception("Probe '%s' using '%s' failed", method, executable)
                return  # type: ignore

            _log.exception(
                "Probe '%s' using '%s' failed, trying fallback", method, executable
            )
            try:
                codec, bitrate = await loop.run_in_executor(None, lambda: fallback(source, executable))  # type: ignore
            except Exception:
                _log.exception("Fallback probe using '%s' failed", executable)
            else:
                _log.info("Fallback probe found codec=%s, bitrate=%s", codec, bitrate)
        else:
            _log.info("Probe found codec=%s, bitrate=%s", codec, bitrate)
        finally:
            return codec, bitrate

    @staticmethod
    def _probe_codec_native(
        source, executable: str = "ffmpeg"
    ) -> tuple[str | None, int | None]:
        exe = (
            f"{executable[:2]}probe"
            if executable in {"ffmpeg", "avconv"}
            else executable
        )

        args = [
            exe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-select_streams",
            "a:0",
            source,
        ]
        output = subprocess.check_output(args, timeout=20)
        codec = bitrate = None

        if output:
            data = json.loads(output)
            streamdata = data["streams"][0]

            codec = streamdata.get("codec_name")
            bitrate = int(streamdata.get("bit_rate", 0))
            bitrate = max(round(bitrate / 1000), 512)

        return codec, bitrate

    @staticmethod
    def _probe_codec_fallback(
        source, executable: str = "ffmpeg"
    ) -> tuple[str | None, int | None]:
        args = [executable, "-hide_banner", "-i", source]
        proc = subprocess.Popen(
            args,
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        out, _ = proc.communicate(timeout=20)
        output = out.decode("utf8")
        codec = bitrate = None

        codec_match = re.search(r"Stream #0.*?Audio: (\w+)", output)
        if codec_match:
            codec = codec_match.group(1)

        br_match = re.search(r"(\d+) [kK]b/s", output)
        if br_match:
            bitrate = max(int(br_match.group(1)), 512)

        return codec, bitrate

    def read(self) -> bytes:
        return next(self._packet_iter, b"")

    def is_opus(self) -> bool:
        return True