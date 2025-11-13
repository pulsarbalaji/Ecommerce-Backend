import os
from django.conf import settings
from django.contrib.staticfiles import finders
import urllib

def get_display_product(product):
    """
    Logic for deciding which product (main or variant) to show:
    1️⃣ If main product is in stock → show itself.
    2️⃣ Else if any variant is available → show first available variant.
    3️⃣ Else show main product (as out of stock).
    """
    # 1️⃣ If product itself has stock → show main
    if product.stock_quantity > 0 and product.is_available:
        return product

    # 2️⃣ Try to find first available variant
    variant = product.variants.filter(is_available=True, stock_quantity__gt=0).first()
    if variant:
        return variant

    # 3️⃣ No variants in stock → show parent anyway (to show "Out of Stock")
    return product

from num2words import num2words

def amount_in_words_indian(amount):
    """
    Return Indian currency words in a proper readable format.
    Works even if num2words doesn't support en_IN.
    """
    words = num2words(amount, to='currency', lang='en')
    words = words.replace("euro", "rupees").replace("euros", "rupees")
    words = words.replace("cent", "paise").replace("cents", "paise")
    return f" {words.capitalize()}"

def link_callback(uri, rel):
    """
    Convert URIs to absolute file system paths for xhtml2pdf.
    Works for /static/, file://, and raw Windows paths.
    """
    # Case 1: Django static file
    if uri.startswith(settings.STATIC_URL):
        path = finders.find(uri.replace(settings.STATIC_URL, ""))
        if path:
            return os.path.realpath(path)

    # Case 2: file:// absolute path
    if uri.startswith("file://"):
        path = urllib.parse.urlparse(uri).path
        if path.startswith("/") and os.name == "nt" and ":" in path:
            path = path.lstrip("/")
        return os.path.realpath(path)

    # Case 3: raw Windows path (e.g., C:\...)
    if os.path.exists(uri):
        return os.path.realpath(uri)

    raise Exception(
        f"Media URI must start with {settings.STATIC_URL} or file:// or be a valid path. Got: {uri}"
    )