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
