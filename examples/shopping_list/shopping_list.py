import os
from decimal import Decimal

from te_tree.tkgui import Mainwin
from te_tree.tkgui.editor import Editor_Tk, Lang_Object  # type: ignore
from te_tree.core.editor import blank_case_template, new_editor, freeatt_child  # type: ignore
from te_tree.config import load_config

# Load the configuration file from the example's folder
config_dir = os.path.dirname(os.path.abspath(__file__))
config = load_config(os.path.join(config_dir, "config.json"))
# Exit, if the configuration file is not found
if config is None:
    print("Error when loading configuration.")
    exit(1)

# A case is a top-level item in the app and is potential ancestor for all other items.
# There has to be a template defined for the app's cases.
case_template = blank_case_template()

# The currency is set at the level of case template. This determines the symbol, with which the
# monetary values are stored in the xml files, that store the data edited in the app.
case_template.configure(currency=config.currency)

# Define attribute types used by the various items
# The cost is a monetary attribute type, with default value 0 and with condition to be
# always non-negative
cost = case_template.attr.money(0, custom_condition=lambda x: x >= 0)
# A item description is a text-based attribute type, with default value being empty string
description = case_template.attr.text("")


# Define function determining value of a total per item group
# This function sums up two types of prices - an item price and the total per group
def total_price_func(individual, totals) -> Decimal:
    return sum(individual) + sum(totals)


# Now use this function by defining dependency via the case template
total_price = case_template.dependency(
    "total", total_price_func, freeatt_child("price", cost), freeatt_child("total", cost)
)

# Define the items manipulated by the app
# First define item "Item", that has a two attributes - a price (cost type)
# and description (description type)
case_template.add(
    "Item",
    {"price": cost, "description": description},
    child_template_labels=(),
    dependencies=[],
)
# The second is the "Group", that serves as a parent item both for Items and other Groups
case_template.add(
    "Group",
    {"total": cost, "description": description},
    child_template_labels=("Item", "Group"),
    dependencies=[total_price],
)

# Make the Items mergeable. When merging items, their prices are summed up, while their
# descriptions are concatenated
case_template.add_merging_rule(
    "Item",
    {"price": "sum", "description": "join_texts"},
)

# Now for the case itself, define its attributes and the type of items, that
# the case can be parent of
case_template.set_case_template(
    {"total": cost}, child_template_labels=("Item", "Group"), dependencies=[total_price]
)

# Also, make group to be insertable as a case
case_template.set_insertable("Group")

# Define the UI using the loaded configuration
# Create the main window
win = Mainwin()
win.title(config.application_name)
# Language object imports and contains translations for all UI parts
curr_dir = os.path.abspath(os.path.dirname(__file__))
locpath = os.path.join(curr_dir, "localization", f"{config.localization}.xml")
lang = Lang_Object.get_lang_object(locpath)
# The editor provides access to all the items accessible from the app
editor = new_editor(
    case_template,
    config.localization,
    lang=lang,
    ignore_duplicit_names=config.allow_item_name_duplicates,
)
# Create the editor UI
editor_ui = Editor_Tk(
    editor=editor,
    master_window=win,
    displayable_attributes=({"price": ("price", "total")}),
    lang=lang,
    icons={
        "Item": os.path.join(curr_dir, "icons/item.png"),
        "Group": os.path.join(curr_dir, "icons/group.png"),
    },
)
editor_ui.configure(
    precision=config.editor_precision,
    trailing_zeros=config.show_trailing_zeros,
    use_thousands_separator=config.use_thousands_separator,
)

# Open the app
win.open()
