import os
import readline

from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

#Setup some helper variables
input_files = {}
chosen_file = ""
selected_element_for_chapters = ""
selected_attrib_for_chapters = ""
offset = 0

# define help function
def help_screen():
    print("""
    
        Some useful concepts:

            Current File: From Menu Option 1, this is the file you want to work on.

            Current Element: From Menu Option 2, this is the element that demarcates chapter boundaries.

            Current Attirbute: From Menu Option 2, this is the attribute that specifies which elements are to be used for chapter boundaries. 
                                (e.g. <div class="chapter"> and not <div id="the_nothing">.)
            
            Current Offset: From Menu Option 3, this is the number of your chosen element that should be skipped before writing chapters.
                                Why? Because sometimes encoders use the same elements for unrelated, extra-textual matters.                    
             
    """)
    choice = input("\nPress enter to return to the main menu")
    if choice is not None:
        menu()

# define our clear function
def screen_clear():
    #see: https://student.cs.uwaterloo.ca/~cs452/terminal.html
    print("\033[H\033[J")

# generate a list of files in input/
def generate_input_list():
    screen_clear()
    i = 1
    #Generate List of Texts in input directory for Menu
    directory = 'input'

    for file in os.listdir(directory):
        f = os.path.join(directory, file)
        #Make sure it's a file
        if os.path.isfile(f):
            input_files[i] = f
            i += 1

    input_files["C"] = "Clear selection"
    input_files["M"] = "Return to Main Menu"

    table = Table(title=f"Source Files", show_lines=True)
    table.add_column("Option", style="cyan", no_wrap=True)
    table.add_column("File", justify="left", style="magenta")
    
    for item,value in input_files.items():
        table.add_row(str(item), value)
    
    console = Console()
    console.print(table)
    
    print("\n")

    get_file_choice()

def get_file_choice():
    #These are the menu choices and the corresponding functions:
    global chosen_file
    global selected_attrib_for_chapters
    global selected_element_for_chapters
    global offset

    choice = input("Enter the number of the file you'd like to use: ")
    if choice.lower() == "c":
        chosen_file = ""
        menu()
    elif choice.lower() == "m":
        #Don't erase a choice if it exists, but pass an empty value if it doesn't
        menu()
    elif choice in str(input_files.keys()):
        choice = int(choice)
        if input_files.get(choice) is not None:
            chosen_file = input_files[choice]
            #Clear file-specifc values when choosing a new file
            selected_attrib_for_chapters = ""
            selected_element_for_chapters = ""
            offset = 0
            menu()
    else:
        print("Sorry, that's not a valid choice. Try again.\n")
        get_file_choice()

def get_menu_choice():
    global selected_attrib_for_chapters
    global selected_element_for_chapters
    global offset

    #These are the menu choices and the corresponding functions:
    choice = input("Select an option from the menu above: ")
    if choice == '1':
        generate_input_list()
    elif choice == '2':
        get_element_count_in_chosen_file()
    elif choice == '3':
        see_samples_chooser(selected_element_for_chapters)
    elif choice == '4':
        process_html(chosen_file, selected_element_for_chapters, selected_attrib_for_chapters, offset)
    elif choice.lower() == 'a':
        selected_attrib_for_chapters = ""
        menu()
    elif choice.lower() == 'e':
        selected_element_for_chapters = ""
        menu()
    elif choice.lower() == 'h':
        help_screen()
    elif choice.lower() == 'o':
        offset = 0
        menu()
    elif choice.lower() == 'q':
        print("\nOk, quitting...\n")
        quit()
    else:
        print("Sorry, that's not a valid choice. Try again.\n")
        get_menu_choice()

def get_offset_choice(element):
    global offset
    #Count the number of 'element' that happen before the chapters begin, and subtract from 1 to get the right starting place for this counter.
    choice = input(f"Define offset (how many of these {element} to ignore): ")
    if choice is not None:
        try:
            int(choice)
            offset = int(choice)
        except ValueError:
            choice = ""

        menu()

def get_element_count_in_chosen_file():
    screen_clear()
    #Placeholder dict for element counts
    counts_dict = {}
    #Get File contents
    with open(chosen_file, "r", encoding="utf-8") as file:
        contents = file.read()
    #Soupify Contents
    soup = BeautifulSoup(contents, "html.parser")

    for element in soup.find_all():
        name = element.name
        if name not in counts_dict:
            counts_dict[name] = 1
        else:
            counts_dict[name] += 1

    #Print dictionary in order by largest value
    sort_counts_dict = sorted(counts_dict.items(), key=lambda x: x[1], reverse=True)
    table = Table(title=f"Elements in {chosen_file}")
    table.add_column("Count", style="cyan", no_wrap=True)
    table.add_column("element", justify="left", style="magenta")
    
    for item, value in sort_counts_dict:
        table.add_row(str(value), item)
    
    console = Console()
    console.print(table)

    choice = input("\nGive me an element name to look deeper, or 'M' to return to menu: ")
    if choice.lower() == "m":
        menu()
    elif choice in counts_dict.keys():
        dig_deeper(choice, soup)
    else:
        screen_clear()
        get_element_count_in_chosen_file()

def dig_deeper(selected_element, soup):
    global selected_element_for_chapters
    global selected_attrib_for_chapters
    class_counts = {}
    id_counts = {}

    for element in soup.find_all(selected_element):
        if element.has_attr("class"):
            temp = element['class'][0]
            if temp not in class_counts.keys():
                class_counts[temp] = 1
            else:
                class_counts[temp] += 1
    for element in soup.find_all(selected_element):
        if element.has_attr("id"):
            temp = element['id'][0]
            if temp not in id_counts.keys():
                id_counts[temp] = 1
            else:
                id_counts[temp] += 1

    #Print banner
    screen_clear()
    print("To use this element without attributes, enter '2'.\n")
    print("To use this element, and an attribute, enter the attribute.\n")

    #Print dictionaries in order by largest value
    sort_class_counts_dict = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)
    sort_id_counts_dict = sorted(id_counts.items(), key=lambda x: x[1], reverse=True)

    table = Table(title="Classes and IDs")
    table.add_column("Count", style="cyan", no_wrap=True)
    table.add_column("element", justify="left", style="magenta")
    table.add_column("type", justify="right", style="magenta")
    if len(class_counts.items()) > 0:
        for item, value in sort_class_counts_dict:
            table.add_row(str(value), item, "class")
    if len(id_counts.items()) > 0:
        for item, value in sort_id_counts_dict:
            table.add_row(str(value), item, "id")
    
    #Only print table if it has contents
    if table.rows:
        console = Console()
        console.print(table)
    else:
        print("\nNo classes or IDs for this element.\n")

    print("\n")
    print("1.\tExamine another element")
    print("2.\tUse this element to find chapters")
    print("M.\tBack to main menu")
    print("\n")
    choice = input("Select an attribute to use for chapter selection, or another menu choice: ")

    if choice in (class_counts.keys() or id_counts.keys()):
        selected_attrib_for_chapters = choice
        selected_element_for_chapters = selected_element
        menu()
    elif choice == "1":
        screen_clear()
        get_element_count_in_chosen_file()
    elif choice == "2":
        selected_element_for_chapters = selected_element
        menu()
    elif choice.lower() == "m":
        menu()
    else:
        choice = input("What's next? ")

def see_samples_chooser(element):
    container_elems = ["div"]

    if element in container_elems:
        see_samples_of_container_element(chosen_file, selected_element_for_chapters, selected_attrib_for_chapters)
    else:
        see_samples_of_non_container_element(chosen_file, selected_element_for_chapters, selected_attrib_for_chapters)

def see_samples_of_non_container_element(the_file, element, attribute):
    #Counter for display
    j = 1

    with open(the_file, "r", encoding="utf-8") as file:
        contents = file.read()
    #Soupify Contents
    soup = BeautifulSoup(contents, "html.parser")

    samples = soup.find_all(element, attribute)
    temp_samples = []

    #Check that sample has text, if it doesn't then look to the next element (and its children) to see if we can find something.
    for sample in samples:
        if sample.get_text():
            temp_samples.append(sample.get_text())
        else:
            sample = sample.next_element
            #TODO: Anything that isn't nothing or a space will count. Might want to revisit.
            if len(sample.get_text()) > 1:
                temp_samples.append(sample.get_text())
            else:
                #Ok, next element was a dud. Does it have kids?
                for child in sample.next_element.children:
                    if len(child.get_text()) > 1:
                        temp_samples.append(child.get_text())
                        break
    if len(temp_samples) > 10:
        for item in temp_samples[:10]:
            print(f"Item number {j}: " + item + "\n")
            j += 1
    else:
        for item in temp_samples[:5]:
            print(f"Item number {j}: " + item + "\n")
            j += 1

    get_offset_choice(element)

def see_samples_of_container_element(the_file, element, attribute):
    #Counter for display
    j = 1

    with open(the_file, "r", encoding="utf-8") as file:
        contents = file.read()
    #Soupify Contents
    soup = BeautifulSoup(contents, "html.parser")

    samples = soup.find_all(element, attribute)
    temp_samples = []
    for sample in samples:
        temp_samples.append(sample.get_text())

    if len(temp_samples) > 10:
        j = 1
        for item in temp_samples[:10]:
            print(f"Item number {j}: " + item[0:100] + "...\n")
            j += 1
    else:
        for item in temp_samples[:5]:
            j = 1
            print(f"Item number {j}: " + item[0:100] + "...\n")
            j += 1

    get_offset_choice(element)

def generate_menu_meta_table():
    the_file = chosen_file
    the_element = selected_element_for_chapters
    the_attrib = selected_attrib_for_chapters
    the_offset = str(offset)
    table = Table(title="Status")

    table.add_column("Current File", justify="center", style="cyan", no_wrap=True)
    table.add_column("Current Element", justify="center", style="magenta")
    table.add_column("Current Attribute", justify="center", style="green")
    table.add_column("Current Offset", justify="center", style="yellow")


    table.add_row(the_file, the_element, the_attrib, the_offset)

    console = Console()
    console.print(table)

def menu():
    screen_clear()
    print("\n")
    generate_menu_meta_table()
    print("\n")
    print("What would you like to do?:\n")
    print("1.\tSelect a Working File")
    print("2.\tAnalyze Working File")
    print("3.\tSee Samples of Element/Attribute")
    print("4.\tProcess the File")
    print("\n")
    print("A.\tClear Current Attribute Choice")
    print("E.\tClear Current Element Choice")
    print("O.\tClear Current Offset")
    print("H.\tHelp!")
    print("Q.\tQuit")
    print("\n")
    get_menu_choice()

#Process the XML and output HTML elements for the body.
def process_html(the_file, element, attrib, off):
    #Setup
    output_dir = the_file.split('/')[1]
    output_dir = output_dir.split('.')[0]
    if not os.path.exists(f'output/{output_dir}'):
        os.makedirs(f'output/{output_dir}')

    container_elems = ["div"]

    #Read elements from the body.
    with open(the_file, "r", encoding="utf-8") as file:
        #Read the file
        contents = file.read()

        #Make some soup
        soup = BeautifulSoup(contents, "html.parser")

        #Get all the TEI headings
        elements = soup.find_all(element, attrib)

        #Ok, some elements have children and some siblings. Process accordingly.
        #TODO: List is manually updated for now...improve?

        if element in container_elems:
            #Since we have known chapter divisions, we can start numbering at 1.
            #TODO: evaluate this more thoroughly
            process_container_element(off, output_dir, elements)
        else:
            process_non_container_element(off, output_dir, elements)

def process_non_container_element(off, output_dir, elements):
    global selected_attrib_for_chapters
    global selected_element_for_chapters

    chapter_content = ""
    i = (1 - off)
    for elem in list(elements):
        chapter_content += elem.get_text()
        for sibling in elem.next_siblings:
            if sibling.next_element.name == f'{selected_element_for_chapters}' or sibling.name == 'pre' or sibling.next_sibling == None:
                if i > 0:
                    with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                        output_file.write(chapter_content)
                i += 1
                chapter_content = ""
                break
            else:
                chapter_content += sibling.get_text()

def process_container_element(off, output_dir, elements):
    chapter_content = ""
    i = (1 - off)

    for elem in list(elements):
        chapter_content += elem.get_text()
        for child in elem.children:
            if selected_attrib_for_chapters != "":
                if child.next_element.name == selected_element_for_chapters:
                    if not child.next_element.has_attr(selected_attrib_for_chapters):
                        chapter_content += child.get_text()
                else:
                    if i > 0:
                        with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                            output_file.write(chapter_content)

        i += 1
        chapter_content = ""

menu()
