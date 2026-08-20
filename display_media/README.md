# Display media

`local/` is an optional checkout-local still-image library for Panel Control.
Place generic local `.png`, `.jpg`, or `.jpeg` files there manually, then choose
**Refresh folder** in the app. Its contents are ignored by Git and excluded
from source and wheel packages; only this explanation and the empty-folder
marker belong in version control.

Personal images do not need to enter the project tree. **Browse / Choose
image** can select a PNG or JPEG directly from a private location such as the
user's Pictures directory. The file is decoded and prepared in memory for the
current app session and is not copied into the repository or media library.

Do not place media intended for publication in `local/`. If public sample media
is added in a future milestone, it should use a separate reviewed directory
with explicit asset provenance and licensing.
