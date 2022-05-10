1. Deal with sample preview for elements like `<hr>` that are self-closing (get siblings instead)
2. Create handler to select type of sample view (container v. non)
3. ~~Texts like [this](https://www.gutenberg.org/files/68033/68033-h/68033-h.htm) have busted HTML (divs marked chapter that are just headings, and the siblings are the meat). Handle it.~~ Handled.
    - ~~Also busted: [this guy](https://www.gutenberg.org/files/68034/68034-h/68034-h.htm) (need siblings from `<hr>` elements to get chapters...)~~
4. Create a more interactive processing mode for ornery texts.