import io
import os

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {'PNG', 'JPEG', 'WEBP'}
FILE_TYPES = [('Images', '*.png *.jpg *.jpeg *.webp')]


class ImageError(ValueError):
    pass


def sanitize_image(data, max_bytes=MAX_IMAGE_BYTES):
    try:
        with Image.open(io.BytesIO(data)) as source:
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise ImageError('Only PNG, JPG, and WEBP images are allowed; SVG is prohibited.')
            image = ImageOps.exif_transpose(source)
            image.load()
            has_alpha = image.mode in ('RGBA', 'LA') or 'transparency' in image.info
            image = image.convert('RGBA' if has_alpha else 'RGB')
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageError('The selected file is not a valid PNG, JPG, or WEBP image.') from exc

    attempts = []
    if has_alpha:
        attempts.extend([('PNG', {}), ('WEBP', {'quality': 88, 'method': 6})])
    else:
        attempts.extend([('JPEG', {'quality': quality, 'optimize': True}) for quality in (90, 82, 72, 60, 48)])
        attempts.append(('WEBP', {'quality': 70, 'method': 6}))

    current = image
    for scale in (1.0, 0.85, 0.7, 0.55, 0.4):
        if scale != 1.0:
            current = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
        for output_format, options in attempts:
            output = io.BytesIO()
            candidate = current
            if output_format == 'JPEG' and candidate.mode != 'RGB':
                background = Image.new('RGB', candidate.size, 'white')
                background.paste(candidate, mask=candidate.getchannel('A'))
                candidate = background
            candidate.save(output, format=output_format, **options)
            result = output.getvalue()
            if len(result) <= max_bytes:
                return result, output_format.lower().replace('jpeg', 'jpg')
    raise ImageError('The image could not be compressed below 5 MB.')


def prepare_image(path):
    if os.path.splitext(path)[1].lower() == '.svg':
        raise ImageError('SVG images are prohibited.')
    with open(path, 'rb') as image_file:
        return sanitize_image(image_file.read())
