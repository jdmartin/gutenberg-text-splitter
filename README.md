# gutenberg-text-splitter
Experimental tool for splitting texts from Project Gutenberg into chapters

### What is this?

This program aims to allow you to download an HTML version of a book on [Project Gutenberg](https://www.gutenberg.org/) and separate it into chapters for further processing.

### Assumptions
Right now, the code works well with well-formed HTML.  So, it is assumed you are using a document that is well-formed.

If you are processing a file where chapter content is enclosed inside `<div>`, then the program will see the `<div>` and grab all children until the next one (or the end of the file).

If you are processing a file where chapter content is only demarcated by `<h2>` or `<h2>` or something like this, then then program will grab all siblings of these elements until the next one (or the end of the file).

This is not a perfect system, and improvements are being devised.

### An Example of _Bad_ HTML:

Take [this book](https://www.gutenberg.org/files/68033/68033-h/68033-h.htm) (please). This book uses `<div class="chapter">`, but then only encloses titles in these sections. Books like this require a bit more planning in order to get both title and chapter content.

### Ok, Ok, but how do I use it?!

Using the program is a four-part process.

0. Install the program:
    - Create a new virtual environment to hold this.
    - Clone the repo to your new environment.
    - Install dependencies with `pip install -r requirements.txt`, `poetry install`, or similar.
1. Drop any HTML formatted book into the input folder, or use one of the built-ins.
2. Execute the program via `python3 ./splitter.py`

Now that the program is running...

1. Choose a file to work with.
2. Analyze the file to see what element/attribute you want to select for chapter detection.
    - N.B. Selecting an element will show you any classes or IDs on elements of that type to help narrow down your choice.
3. Once you have decided on your element/attribute pair, you can see samples of those selections to help you choose an offset.
    - N.B. On irregularly constructed documents, there are often "chapters" that are really just prefaratory matter.  The offset allows you to say how many there and then chapter selections won't start until you've passed an offset number of those elements.
4. Now, you can process the file.
    - Files will be written to output/title/chapter_n
      - Ex: If your file is called joe.html, then the output is in output/joe/chapter_n.

