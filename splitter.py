import os

from bs4 import BeautifulSoup
from pydoc import pager
from rich import print
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

console = Console()

class Editor:
    def __init__(self):
        self.chosen_file = ""
        self.selected_element_for_chapters = ""
        self.selected_attrib_for_chapters = ""
        self.excluded_attribs_for_chapters = []
        self.offset = 0
        self.completed_files = []
        return

    def main():
        
        # define help function
        def help_screen():
            print("""
            
                Some useful concepts:

                    [red]Current File[/red]: From Menu Option 1, this is the file you want to work on.

                    [red]Current Element[/red]: From Menu Option 2, this is the element that demarcates chapter boundaries.

                    [red]Current Attirbute[/red]: From Menu Option 2, this is the attribute that specifies which elements are to be used for chapter boundaries. 
                                        (e.g. <div class="chapter"> and not <div id="the_nothing">.)
                    
                    [red]Current Offset[/red]: From Menu Option 3, this is the number of your chosen element that should be skipped before writing chapters.
                                        Why? Because sometimes encoders use the same elements for unrelated, extra-textual matters. 

                    N.B. (Exploring the source pipes the file to less. Use /pattern to highlight pattern ahead, or [bold magenta]?pattern[/bold magenta] for behind.)                   
                    
            """)
            choice = console.input("\nPress [bold green]enter[/bold green] to return to the main menu")
            if choice is not None:
                menu()

        # define our clear function
        def screen_clear():
            console.clear()

        # generate a list of files in input/
        def generate_input_list():
            input_files = {}
            screen_clear()
            i = 1
            #Generate List of Texts in input directory for Menu
            directory = 'input'

            for file in sorted(os.listdir(directory)):
                f = os.path.join(directory, file)
                #Make sure it's a file
                if os.path.isfile(f):
                    input_files[i] = f
                    i += 1

            table = Table(title="Source Files", show_lines=True)
            table.add_column("Option", style="cyan", no_wrap=True)
            table.add_column("File", justify="left", style="magenta")
            
            for item,value in input_files.items():
                table.add_row(str(item), value)
            
            console.print(table)
            
            print("\n")

            def get_file_choice(files):
                #These are the menu choices and the corresponding functions:
                file_selection = the_program.chosen_file
                choice = console.input("Enter the number of the file you'd like to use, or '[bold green]M[/bold green]' for the Main Menu: ")
                valid_keys = set(input_files.keys())

                if choice.lower() == "m":
                    #Don't erase a choice if it exists
                    return

                if choice.lower() not in str(valid_keys):
                    print("Sorry, that's not a valid choice. Try again.\n")
                    get_file_choice(files)
                else:
                    choice = int(choice)
                    file_selection = files.get(choice)
                    the_program.chosen_file = file_selection
                    #Clear file-specifc values when choosing a new file
                    the_program.selected_attrib_for_chapters = ""
                    the_program.selected_element_for_chapters = ""
                    the_program.offset = 0
                
            get_file_choice(input_files)

        def get_menu_choice():
            #These are the menu choices and the corresponding functions:
            choice = console.input("Select an option from the menu above: ")
            if choice == '1':
                generate_input_list()
            elif choice == '2':
                if the_program.chosen_file != "":
                    get_element_count_in_chosen_file()
            elif choice == '3':
                if the_program.chosen_file != "":
                    see_samples_chooser(the_program.selected_element_for_chapters)
            elif choice == '4':
                if the_program.chosen_file != "":
                    process_html(the_program.chosen_file, the_program.selected_element_for_chapters, the_program.selected_attrib_for_chapters, the_program.offset)
            elif choice.lower() == 's':
                if the_program.chosen_file != "":
                    with open(the_program.chosen_file, 'r') as source_file:
                        source_contents = source_file.read()
                        syntax = Syntax(source_contents, "html", line_numbers=True)
                        with console.pager():
                            console.print(syntax)
            elif choice.lower() == 'a!':
                the_program.selected_attrib_for_chapters = ""
            elif choice.lower() == 'c!':
                the_program.chosen_file = ""
                the_program.selected_attrib_for_chapters = ""
                the_program.selected_element_for_chapters = ""
                the_program.offset = 0
            elif choice.lower() == 'e!':
                the_program.selected_element_for_chapters = ""
            elif choice.lower() == 'h':
                help_screen()
            elif choice.lower() == 'o!':
                the_program.offset = 0
            elif choice.lower() == 'q':
                print("\nOk, quitting...\n")
                quit()
            else:
                print("Sorry, that's not a valid choice. Try again.\n")
                get_menu_choice()

        def get_offset_choice(element):
            #Count the number of 'element' that happen before the chapters begin, and subtract from 1 to get the right starting place for this counter.
            choice = console.input(f"\nDefine offset (how many of these {element} to ignore) (or enter keeps current value: {the_program.offset}): ")
            if choice == "":
                return
            else:
                try:
                    int(choice)
                    the_program.offset = int(choice)
                except ValueError:
                    choice = ""
            
        def get_element_count_in_chosen_file():
            screen_clear()
            #Placeholder dict for element counts
            counts_dict = {}
            suggested_items = []
            #Get File contents
            with open(the_program.chosen_file, "r", encoding="utf-8") as file:
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
            table = Table(title=f"Elements in {the_program.chosen_file}", min_width=60)
            table.add_column("Count", style="cyan", no_wrap=True)
            table.add_column("element", justify="left", style="magenta")
            
            for item, value in sort_counts_dict:
                table.add_row(str(value), item)
            
            #Generate some recommendations based on likely useful elements/attributes
            suggest_table, suggested_items = offer_suggestions_about_elements_and_attributes(soup)
            #Generate list of valid choices
            valid_suggestions = []
            for item in suggested_items:
                valid_suggestions += item[0]
            
            #Display the Data
            # TODO: Maybe replace this with a fancy rich.layout?
            console.print(table)
            print("\n")
            console.print(suggest_table)
            print("\n")

            choice = console.input("Give me an element name to look deeper, an option number to use a suggestion, or '[bold green]M[/bold green]' to return to menu: ")
            if choice.lower() == "m":
                menu()
            elif choice in valid_suggestions:                
                for entry in suggested_items:
                    if entry[0] == choice:
                        the_program.selected_element_for_chapters = entry[2]
                        the_program.selected_attrib_for_chapters = entry[3]
                        menu()
            elif choice in counts_dict.keys():
                dig_deeper(choice, soup)
            else:
                screen_clear()
                get_element_count_in_chosen_file()

        def offer_suggestions_about_elements_and_attributes(soup):
            suggested_items = []
            chapter_search_terms = ["chap", "chapter", "x-ebookmarker-drop"]
            chapter_search_results = []
            header_search_terms = ["h2", "h3", "hr"]
            header_search_results = []

            option = 0
            #We're going to go through our list of suggested elements and attributes, count them, assign an option, and add them to the list we'll use to display and handle suggestions
            for item in chapter_search_terms:
                class_count = 0
                element_name = ""
                for thing in soup.find_all(attrs={"class": f"{item}"}):
                    element_name = thing.name
                    class_count += 1
                #Only store result and increment the option if there are results for item.
                if class_count > 0:
                    option += 1
                    chapter_search_results.append([element_name, f"{item}", class_count, str(option)])
            
            for item in header_search_terms:
                class_count = 0
                element_name = ""
                for thing in soup.find_all(f"{item}"):
                    element_name = thing.name
                    class_count += 1
                #Only store result and increment the option if there are results for item.
                if class_count > 0:
                    option += 1
                    header_search_results.append([element_name, f"{item}", class_count, str(option)])

            suggest_table = Table(title=f"Suggested Elements and Attributes in {the_program.chosen_file}", min_width=60, show_lines=True)
            suggest_table.add_column("Option #", justify="left" ,style="purple")
            suggest_table.add_column("Count", style="cyan", no_wrap=True)
            suggest_table.add_column("element", justify="left", style="magenta")
            suggest_table.add_column("attribute", justify="left", style="green")
            
            #Only add things to the table if their count is not 0.
            for item in chapter_search_results:
                if item[2] != 0:
                    suggest_table.add_row(item[3], str(item[2]), item[0], item[1])
                    suggested_items.append([item[3], str(item[2]), item[0], item[1]])

            for item in header_search_results:
                if item[2] != 0:
                    suggest_table.add_row(item[3], str(item[2]), item[0], "")
                    suggested_items.append([item[3], str(item[2]), item[0], ""])

            return suggest_table, suggested_items

        def dig_deeper(selected_element, soup):
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
                    temp = element['id']
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
                console.print(table)
            else:
                text = Text("\n\t__== No classes or IDs for this element. ==__\n")
                text.stylize("cyan")
                console.print(text)

            print("\n")
            print("[bold green]1[/bold green]\tExamine another element")
            print("[bold green]2[/bold green]\tUse this element to find chapters")
            print("[bold green]3[/bold green]\tNegative search (experimental, div attributes only for now)")
            print("[bold green]M[/bold green]\tBack to main menu")
            print("\n")

            choice = console.input("Select an attribute to use for chapter selection, or another menu choice: ")

            if choice in class_counts.keys() or choice in id_counts.keys():
                the_program.selected_attrib_for_chapters = choice
                the_program.selected_element_for_chapters = selected_element
            elif choice == "1":
                screen_clear()
                get_element_count_in_chosen_file()
            elif choice == "2":
                the_program.selected_element_for_chapters = selected_element
            elif choice == "3":
                the_program.selected_element_for_chapters = selected_element
                negative_choices = console.input("Enter a comma-separated list of attributes to exclude: ")
                if negative_choices != "":
                    for neg_choice in negative_choices.split(","):
                        the_program.excluded_attribs_for_chapters.append(neg_choice.strip())
            elif choice.lower() == "m":
                pass
            else:
                dig_deeper(selected_element, soup)

        def see_samples_chooser(element):
            container_elems = ["div"]

            if element in container_elems:
                see_samples_of_container_element(the_program.chosen_file, the_program.selected_element_for_chapters, the_program.selected_attrib_for_chapters)
            else:
                see_samples_of_non_container_element(the_program.chosen_file, the_program.selected_element_for_chapters, the_program.selected_attrib_for_chapters)

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
                #Skip over excluded classes/IDs
                for entry in the_program.excluded_attribs_for_chapters:
                    if entry in sample.attrs:
                        continue

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
            
            show_the_samples(temp_samples)
            
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
                #Skip over excluded classes/IDs
                for entry in the_program.excluded_attribs_for_chapters:
                    if entry in sample.attrs:
                        continue
                temp_samples.append(sample.get_text())
            
            show_the_samples(temp_samples)

            get_offset_choice(element)

        def show_the_samples(temp_samples):
            screen_clear()
            table = Table(title="Offsets and Samples", width=120, show_lines=True)
            table.add_column("Offset", style="cyan", no_wrap=True)
            table.add_column("Sample Text", justify="left", style="magenta")

            if len(temp_samples) > 15:
                j = 1
                for item in temp_samples[:15]:
                    table.add_row(str(j), item[0:120].strip())
                    j += 1
            elif len(temp_samples) >= 10:
                j = 1
                for item in temp_samples[:10]:
                    table.add_row(str(j), item[0:120].strip())
                    j += 1
            else:
                for item in temp_samples[:5]:
                    j = 1
                    table.add_row(str(j), item[0:120].strip())
                    j += 1
            
            console.print(table)

        def generate_menu_meta_table():
            the_file = the_program.chosen_file
            the_element = the_program.selected_element_for_chapters
            the_attrib = the_program.selected_attrib_for_chapters
            the_offset = str(the_program.offset)
            status = ""

            table = Table(title="Status", style="purple", title_style="green")

            table.add_column("Current File", justify="center", style="cyan", no_wrap=True)
            table.add_column("Current Element", justify="center", style="magenta")
            table.add_column("Current Attribute", justify="center", style="green")
            table.add_column("Current Offset", justify="center", style="yellow")
            table.add_column("Complete?", justify="center")

            if the_file in the_program.completed_files:
                status = "[green]Complete![/green]"
            else:
                status = "[yellow]Incomplete![/yellow]"
            
            if the_file == "":
                status = ""

            table.add_row(the_file, the_element, the_attrib, the_offset, status)

            console.print(table)

        #Process the XML and output HTML elements for the body.
        def process_html(the_file, element, attrib, off):
            #Setup
            output_dir = the_file.split('/')[1]
            output_dir = output_dir.split('.')[0]
            if not os.path.exists(f'output/{output_dir}'):
                os.makedirs(f'output/{output_dir}')

            container_elems = ["div"]

            #Define the functions that will do the work:
            def process_non_container_element(off, output_dir, elements, element, attrib):
                chapter_content = ""
                i = (1 - off)
                
                for elem in list(elements):
                    chapter_content += elem.get_text()
                    for sibling in elem.next_siblings:
                        if "PROJECT GUTENBERG EBOOK" in sibling.text:
                            if i > 0:
                                with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                                    output_file.write(chapter_content)
                            i += 1
                            return

                        if sibling.next_element.name == f'{element}' or sibling.next_sibling == None:
                            if i > 0:
                                with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                                    output_file.write(chapter_content)
                            i += 1
                            chapter_content = ""
                            break
                        else:
                            chapter_content += sibling.get_text()

            def process_container_element(off, output_dir, elements, element, attrib):
                chapter_content = ""
                i = (1 - off)

                for elem in list(elements):
                    chapter_content += elem.get_text()
                    #TODO Make sure this set of conditions triggers as expected.
                    if "PROJECT GUTENBERG EBOOK" in elem.next_element.text:
                            if i > 0:
                                with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                                    output_file.write(chapter_content)
                            break
                    
                    for child in elem.children:
                        if the_program.excluded_attribs_for_chapters is not None:
                            if child.next_element.name == element:
                                for entry in the_program.excluded_attribs_for_chapters:
                                    if not child.next_element.has_attr(entry):
                                        chapter_content += child.get_text()
                            else:
                                if i > 0:
                                    with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                                        output_file.write(chapter_content)
                                
                        elif attrib != "":
                            if child.next_element.name == element:
                                if not child.next_element.has_attr(attrib):
                                    chapter_content += child.get_text()
                            else:
                                if i > 0:
                                    with open(f"output/{output_dir}/chapter_" + str(i), "w", encoding="utf-8") as output_file:
                                        output_file.write(chapter_content)

                    i += 1
                    chapter_content = ""

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
                    process_container_element(off, output_dir, elements, element, attrib)
                else:
                    process_non_container_element(off, output_dir, elements, element, attrib)
                
                the_program.completed_files.append(the_file)

        def menu():
            screen_clear()
            print("\n")
            generate_menu_meta_table()
            print("\n")
            print("What would you like to do?:\n")
            print("[bold green]1[/bold green]\tSelect a Working File")
            print("[bold green]2[/bold green]\tAnalyze Working File")
            print("[bold green]3[/bold green]\tSee Samples of Element/Attribute")
            print("[bold green]4[/bold green]\tProcess the File")
            print("\n")
            print("[bold green]S[/bold green]\tExamine the source file")
            print("\n")
            print("[bold green]A![/bold green]\tClear Current Attribute Choice")
            print("[bold green]C![/bold green]\tClear Everything")
            print("[bold green]E![/bold green]\tClear Current Element Choice")
            print("[bold green]O![/bold green]\tClear Current Offset")
            print("\n")
            print("[bold green]H[/bold green]\tHelp!")
            print("[bold green]Q[/bold green]\tQuit")
            print("\n")
            get_menu_choice()

        while True:
            menu()

if __name__ == "__main__":
    the_program = Editor()
    Editor.main()