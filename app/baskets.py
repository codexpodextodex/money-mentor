"""The three-basket classification.

S-Bank's teaching idea: every euro you spend falls into one of three baskets.

1. essentials  "Regular essentials"     mandatory and regular   (rent)
2. unexpected  "Unexpected necessities" mandatory and irregular (a broken washing machine)
3. everyday    "Everyday spending"      slips through your fingers (coffees)

The rules below are deliberately simple and readable, so a customer can be
told exactly why a payment landed where it did. They use only what the data
holds: transaction type, category, merchant category code (MCC) and size.

Money that is not spending (savings, transfers to your own accounts, income)
gets a `flow` but no basket.
"""

from __future__ import annotations

# A purchase this large in Home & Tech or Transportation looks like replacing
# or repairing something (a washing machine, a car repair), not a routine buy.
BIG_PURCHASE_EUR = 300

# An everyday purchase this small is easy to forget: the "coffee" kind.
SMALL_PURCHASE_EUR = 15

BASKETS = {
    "essentials": {
        "name": "Regular essentials",
        "short": "Essentials",
        "emoji": "🏠",
        "meaning": "Mandatory and regular: you have to pay it, and you can predict it.",
        "examples": "housing, utility bills, groceries, public transport, fuel, parking",
    },
    "unexpected": {
        "name": "Unexpected necessities",
        "short": "Unexpected",
        "emoji": "🔧",
        "meaning": "Mandatory but irregular: you have to pay it, but you cannot tell when.",
        "examples": f"doctor, dentist, pharmacy, a repair or replacement of EUR {BIG_PURCHASE_EUR} or more",
    },
    "everyday": {
        "name": "Everyday spending",
        "short": "Everyday",
        "emoji": "☕",
        "meaning": "Your own choice: small and large things that slip through your fingers.",
        "examples": "restaurants, bars, entertainment, shopping, taxis, travel, small home and tech buys",
    },
}

BASKET_ORDER = ["essentials", "unexpected", "everyday"]

# The same rules as plain sentences, shown to the user on request.
RULES_TEXT = [
    "Housing payments and utility bills are Regular essentials.",
    "Groceries are Regular essentials.",
    f"Transportation is a Regular essential (public transport, fuel, parking), except taxis, which are Everyday spending, and single payments of EUR {BIG_PURCHASE_EUR} or more, which are Unexpected necessities (a repair).",
    "Health (doctor, dentist, pharmacy) is an Unexpected necessity: necessary, but you cannot plan when.",
    f"Home & Tech purchases of EUR {BIG_PURCHASE_EUR} or more are Unexpected necessities (replacing something that broke); smaller ones are Everyday spending.",
    "Restaurants, entertainment, lifestyle shopping and travel are Everyday spending.",
    "Investment deposits are savings, and transfers to your own other accounts are transfers. Neither counts as spending.",
]

# SQL: what kind of money movement a row is.
FLOW_SQL = """
CASE
    WHEN tx_type IN ('salary', 'other_income') THEN 'income'
    WHEN tx_type = 'investment_withdrawal' THEN 'from_savings'
    WHEN tx_type = 'investment_deposit' THEN 'to_savings'
    WHEN tx_type = 'salary_sweep' THEN 'transfer_out'
    WHEN amount > 0 THEN 'income'
    ELSE 'spend'
END
"""

# SQL: which basket a spending row belongs to (NULL when it is not spending).
BASKET_SQL = f"""
CASE
    WHEN tx_type IN ('salary', 'other_income', 'investment_withdrawal', 'investment_deposit', 'salary_sweep') THEN NULL
    WHEN amount > 0 THEN NULL
    WHEN tx_type IN ('housing_payment', 'utilities_payment') THEN 'essentials'
    WHEN category = 'Groceries' THEN 'essentials'
    WHEN category = 'Health' THEN 'unexpected'
    WHEN category = 'Home & Tech' AND -amount >= {BIG_PURCHASE_EUR} THEN 'unexpected'
    WHEN category = 'Transportation' AND mcc = '4121' THEN 'everyday'
    WHEN category = 'Transportation' AND -amount >= {BIG_PURCHASE_EUR} THEN 'unexpected'
    WHEN category = 'Transportation' THEN 'essentials'
    ELSE 'everyday'
END
"""

# Merchant category codes found in the dataset, with plain-language names.
MCC_LABELS = {
    "4111": "Public transport",
    "4121": "Taxis",
    "4511": "Airlines",
    "4722": "Travel agencies",
    "5200": "Home supply stores",
    "5251": "Hardware stores",
    "5411": "Supermarkets",
    "5422": "Meat and frozen food shops",
    "5451": "Dairy shops",
    "5499": "Convenience and specialty food",
    "5541": "Service stations",
    "5542": "Fuel pumps",
    "5651": "Family clothing",
    "5691": "Clothing stores",
    "5712": "Furniture",
    "5732": "Electronics",
    "5734": "Computer software",
    "5812": "Restaurants",
    "5813": "Bars and pubs",
    "5814": "Fast food",
    "5912": "Pharmacies",
    "5941": "Sporting goods",
    "5942": "Book stores",
    "5945": "Hobby, toy and game shops",
    "5999": "Miscellaneous retail",
    "7011": "Hotels",
    "7512": "Car rental",
    "7523": "Parking",
    "7832": "Cinemas",
    "7922": "Theatre and tickets",
    "7991": "Attractions and exhibits",
    "7996": "Amusement parks",
    "7999": "Recreation services",
    "8011": "Doctors",
    "8021": "Dentists",
    "8099": "Medical services",
}

# Names for rows that carry no merchant category code.
TYPE_LABELS = {
    "housing_payment": "Housing payment",
    "utilities_payment": "Utility bills",
    "salary": "Salary",
    "other_income": "Other income",
    "investment_deposit": "Investment deposit",
    "investment_withdrawal": "Investment withdrawal",
    "salary_sweep": "Transfer to own account",
}

SPEND_CATEGORIES = [
    "Housing",
    "Utilities",
    "Groceries",
    "Transportation",
    "Health",
    "Home & Tech",
    "Restaurants",
    "Entertainment",
    "Lifestyle",
    "Travel",
]


def subcategory_sql() -> str:
    """SQL expression for a human-readable subcategory of each row."""
    mcc_cases = "\n".join(f"        WHEN mcc = '{code}' THEN '{label}'" for code, label in MCC_LABELS.items())
    type_cases = "\n".join(f"        WHEN tx_type = '{t}' THEN '{label}'" for t, label in TYPE_LABELS.items())
    return f"""
    CASE
{mcc_cases}
{type_cases}
        WHEN mcc IS NULL THEN category || ' (no card)'
        ELSE category || ' (other)'
    END
    """
