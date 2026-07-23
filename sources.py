"""Per-site configuration for all scrapers.

Endpoints here were each verified live on 2026-06-24. See SPEC.md for field notes.
``key`` is the stable short id stored in the database ``source`` column.
"""

SOURCES = {
    "winedutyfree": {
        "label": "Wine Duty Free",
        "platform": "woocommerce",
        "base": "https://winedutyfree.com",
        "products_path": "/wp-json/wc/store/v1/products",
        "params": {"per_page": 100},
        "category": None,
    },
    "wishbeer": {
        "label": "Wishbeer",
        "platform": "shopify",
        # apex sometimes fails DNS in sandboxes; www host serves products.json directly.
        "base": "https://www.wishbeer.com",
        "products_path": "/collections/wine/products.json",
        "params": {"limit": 250},
        "category": None,
    },
    "winestoreasia": {
        "label": "Wine Store Asia",
        "platform": "magento",
        "base": "https://www.winestoreasia.com",
        "products_path": "/rest/V1/products",
        "params": {"searchCriteria[pageSize]": 250},
        # only keep items that have a wine_type attribute set
        "wine_only_attr": "wine_type",
    },
    "wineplus": {
        "label": "Wine Plus",
        "platform": "woocommerce",
        "base": "https://wineplus.co.th",
        "products_path": "/wp-json/wc/store/v1/products",
        "params": {"per_page": 100},
        "category": None,
        # X-WP-Total header is unreliable here -> paginate until short page
    },
    "spirithouse": {
        "label": "Spirit House",
        "platform": "woocommerce",
        "base": "https://spirithouse.com",
        "products_path": "/wp-json/wc/store/v1/products",
        "params": {"per_page": 100, "category": 50},  # 50 = Wines parent category
        "category": 50,
    },
}

# WooCommerce category names that denote a wine *type* (everything else on those
# sites is treated as a country/region tag).
WINE_TYPE_CATEGORY_HINTS = {
    "red": "Red", "reds": "Red", "red wine": "Red",
    "white": "White", "whites": "White", "white wine": "White",
    "rose": "Rosé", "rosé": "Rosé", "rose wine": "Rosé", "rosé wine": "Rosé",
    "sparkling": "Sparkling", "sparkling wine": "Sparkling",
    "champagne": "Champagne", "champagne & sparkling": "Sparkling",
    "dessert": "Dessert", "dessert wine": "Dessert", "sweet": "Dessert",
    "fortified": "Fortified", "fortified wine": "Fortified", "port": "Fortified",
    "orange": "Orange", "orange wine": "Orange", "orange wines": "Orange",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "(wine-value personal research; contact: tasinpong.k@gmail.com)"
)
