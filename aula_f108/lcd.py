"""Pictures and animations for the keyboard's screen.

The screen is 240x135. What the keyboard stores is not a GIF but raw
frames:

    256-byte header   frame count, then one delay byte per frame (in 2 ms
                      steps), padded with 0xFF
    frames            240x135 pixels each, RGB565 little-endian
    padding           0xFF up to the next 4096-byte page

The keyboard writes whatever it is sent straight to flash and does not
check the size. The slot for the animation holds 141 frames and the
graphics of the built-in menus sit right behind it, so sending more than
that overwrites them for good. Everything in here goes through build(),
which refuses anything over MAX_FRAMES.

Needs Pillow, which is only imported when a picture is actually loaded.
"""

WIDTH = 240
HEIGHT = 135
HEADER_SIZE = 256
PAGE_SIZE = 4096
FRAME_SIZE = WIDTH * HEIGHT * 2

SLOT_FRAMES = 141    # what the keyboard has room for (gif_maxframes in the vendor's config)
MAX_FRAMES = 130     # what this program will send, to stay clear of the edge

DELAY_STEP_MS = 2
MAX_DELAY_MS = 255 * DELAY_STEP_MS

assert MAX_FRAMES <= SLOT_FRAMES


class TooManyFrames(ValueError):
    pass


def rgb565(image):
    """Raw bytes of one frame. `image` is a PIL image of the screen's size."""
    image = image.convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"frame is {image.size}, not {WIDTH}x{HEIGHT}")
    r, g, b = (band.tobytes() for band in image.split())
    out = bytearray(FRAME_SIZE)
    out[0::2] = bytes(((gg << 3) & 0xE0) | (bb >> 3) for gg, bb in zip(g, b))
    out[1::2] = bytes((rr & 0xF8) | (gg >> 5) for rr, gg in zip(r, g))
    return bytes(out)


def fit(image):
    """Scale and crop a picture so it fills the screen."""
    from PIL import Image

    image = image.convert("RGB")
    scale = max(WIDTH / image.width, HEIGHT / image.height)
    size = (max(WIDTH, round(image.width * scale)),
            max(HEIGHT, round(image.height * scale)))
    image = image.resize(size, Image.LANCZOS)
    left = (image.width - WIDTH) // 2
    top = (image.height - HEIGHT) // 2
    return image.crop((left, top, left + WIDTH, top + HEIGHT))


def thin(frames, delays, limit=MAX_FRAMES):
    """Drop frames evenly until there are at most `limit`. The time of a
    dropped frame goes to the one before it, so the speed stays the same."""
    count = len(frames)
    if count <= limit:
        return list(frames), list(delays)
    kept_frames, kept_delays = [], []
    for slot in range(limit):
        start = slot * count // limit
        end = (slot + 1) * count // limit
        kept_frames.append(frames[start])
        kept_delays.append(sum(delays[start:end]))
    return kept_frames, kept_delays


def load(path):
    """Read a picture or an animation. Gives (frames, delays in ms,
    number of frames the file had). Frames are already screen sized and
    already cut down to MAX_FRAMES."""
    from PIL import Image, ImageSequence

    frames, delays = [], []
    with Image.open(path) as image:
        default = image.info.get("duration", 100)
        for frame in ImageSequence.Iterator(image):
            delays.append(frame.info.get("duration", default) or 100)
            frames.append(fit(frame))
    original = len(frames)
    frames, delays = thin(frames, delays)
    return frames, delays, original


def build(frames, delays=None):
    """The bytes to send for a list of frames. `delays` are in ms."""
    count = len(frames)
    if count < 1:
        raise ValueError("no frames")
    if count > MAX_FRAMES:
        raise TooManyFrames(f"{count} frames, the limit is {MAX_FRAMES}")
    delays = list(delays) if delays else [100] * count
    if len(delays) != count:
        raise ValueError("one delay per frame is needed")

    size = HEADER_SIZE + FRAME_SIZE * count
    pages = -(-size // PAGE_SIZE)
    data = bytearray(b"\xFF" * (pages * PAGE_SIZE))
    data[0] = count
    for i, delay in enumerate(delays):
        data[1 + i] = max(1, min(255, round(delay / DELAY_STEP_MS)))
    for i, frame in enumerate(frames):
        start = HEADER_SIZE + i * FRAME_SIZE
        data[start:start + FRAME_SIZE] = rgb565(frame)
    data = bytes(data)
    check(data)
    return data


def check(data):
    """Look over a finished buffer one more time. This is the last thing
    between a buffer and the keyboard, so it doesn't trust build()."""
    if not data or len(data) % PAGE_SIZE:
        raise ValueError("not a whole number of pages")
    count = data[0]
    if count < 1:
        raise ValueError("no frames")
    if count > MAX_FRAMES:
        raise TooManyFrames(f"{count} frames, the limit is {MAX_FRAMES}")
    needed = HEADER_SIZE + FRAME_SIZE * count
    if len(data) != -(-needed // PAGE_SIZE) * PAGE_SIZE:
        raise ValueError("size doesn't match the number of frames")
    if any(b != 0xFF for b in data[1 + count:HEADER_SIZE]):
        raise ValueError("unexpected data in the header")
    return len(data) // PAGE_SIZE


def pages(data):
    return [data[i:i + PAGE_SIZE] for i in range(0, len(data), PAGE_SIZE)]


def seconds(page_count):
    """Roughly how long an upload takes."""
    return page_count * 0.12
