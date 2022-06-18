import os
from os.path import exists

import pandas as pd
import requests
from rich import print
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()
list_of_files = os.listdir('input')

def check_file_exists():
    if not exists('meta/pg_catalog.csv'):
        choice = Confirm.ask("Looks like we don't have the Project Gutenberg catalog. Would you like to download it now?")
        if choice == True:
            url = f'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'

            r = requests.get(url, allow_redirects=False)
            open(f'meta/pg_catalog.csv', 'wb').write(r.content)
        elif choice == False:
            return

    df = pd.read_csv('meta/pg_catalog.csv', low_memory=False)
    return df


def display_results_table(results, type_search):
    if len(results) == 0:
        console.clear()
        input("Sorry, no results. Press enter to return to the search menu.")
        search_menu()
        
    list_of_ids = []
    table = Table(title=f"Results", min_width=60, style="purple", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Author", justify="left", style="magenta")
    table.add_column("Title", justify="left", style="green")
    table.add_column("Subjects", justify="left", style="white")

    for index, row in results.iterrows():
        table.add_row(str(row['Text#']), row['Authors'], row['Title'], row['Subjects'])
        list_of_ids.append(str(row['Text#']))
    
    console.print(table)
    get_selection_by_id(type_search, list_of_ids, results)

def get_name_for_file():
    choice = console.input("\nWhat should I call this file? ([cyan]Note[/cyan]: I just need the name, it will be a .html file by default) \nOr press enter to cancel: ")
    choice = choice.replace('.html', '')
    test_choice = choice + ".html"
    if test_choice == ".html":
        return
    elif test_choice in list_of_files:
        print("Sorry, that name is already taken.")
        get_name_for_file()
    else:
        return choice

def get_selection_by_id(type_search, list_of_ids, results):
    choice = console.input("Which book would you like? You can also enter [bold red]R[/bold red] to refine the results, or just hit enter to select none of these: ")
    if choice in list_of_ids:
        filename = get_name_for_file()
        if filename == None:
            search_menu()
        else:
            download_book_by_id(choice, filename)
    elif choice.lower() == 'r':
        refine_results(results, type_search)
    elif choice == "":
        search_menu()
    else:
        print("Sorry, that's not one of the choices.\n")
        get_selection_by_id(type_search, list_of_ids, results)
        

def download_book_by_id(book_id, filename):
    #Sample Format for HTML File: https://www.gutenberg.org/files/1000/1000-h/1000-h.htm
    #Sample Format for HTML5 File: https://www.gutenberg.org/cache/epub/68033/pg68033-images.html.utf8
    url = f'https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}-images.html.utf8'

    r = requests.get(url, allow_redirects=False)
    if r.status_code == 404:
        print("\nSorry, I can't find an HTML version of that text.")
        input("Press enter to continue...\n")
    if r.status_code == 200:
        open(f'input/{filename}.html', 'wb').write(r.content)

def update_the_catalog():
    cat_url = 'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'
    
    print("Starting download...")
    r = requests.get(cat_url, allow_redirects=False)
    if r.status_code == 404:
        print(f"\nSorry, I can't download that file at this time. Server Responded: {r.status_code}")
        input("Press enter to continue...\n")
    if r.status_code == 200:
        open(f'meta/pg_catalog.csv', 'wb').write(r.content)

def search_for_author(df):
    author_choice = input("What author would you like to find? Or press enter to go back. ")
    if author_choice == "":
        search_menu()
    else:
        try:
            author_results = df.loc[(df['Authors'].str.contains(author_choice, na=False, case=False) & (df['Type']=="Text"))]
            display_results_table(author_results, "author")
        except:
            search_for_author(df)
        

def search_for_title(df):
    title_choice = input("What book would you like to find? Or press enter to go back. ")
    if title_choice == "":
        search_menu()
    else:
        try:
            title_results = df[(df['Title'].str.contains(title_choice, na=False, case=False) & (df['Type']=="Text"))]
            display_results_table(title_results, "title")
        except:
            search_for_title(df)

def search_for_subject(df):
    subject_choice = input("What subject would you like to find? Or press enter to go back. ")
    if subject_choice == "":
        search_menu()
    else:
        try:
            subject_results = df[(df['Subjects'].str.contains(subject_choice, na=False, case=False) & (df['Type']=="Text"))]
            display_results_table(subject_results, "subject")
        except:
            search_for_subject(df)

def refine_results(result_set):
    refinement_type = console.input("Would you like to filter these results by [bold red]A[/bold red]uthor, [bold red]T[/bold red]itle, or [bold red]S[/bold red]ubject? Or press enter to return ")
    refinement = input("Ok, what should I look for? ")
    if refinement == "":
        search_menu()
    elif refinement_type.lower() == 'a':
        new_df = result_set[result_set['Authors'].str.lower().str.contains(refinement.lower())]
        console.clear()
        display_results_table(new_df, "refined")
    elif refinement_type.lower() == 't':
        new_df = result_set[result_set['Title'].str.lower().str.contains(refinement.lower())]
        console.clear()
        display_results_table(new_df, "refined")
    elif refinement_type.lower() == 's':
        new_df = result_set[result_set['Subjects'].str.lower().str.contains(refinement.lower())]
        console.clear()
        display_results_table(new_df, "refined")
    else:
        refine_results(result_set)


def search_menu():
    #console.clear()
    df = check_file_exists()
    print("\n\n\t[underline bold]Search Menu[/underline bold]\n")

    print("\t([bold red]A[/bold red])uthor Search")
    print("\t([bold red]S[/bold red])ubject Search")
    print("\t([bold red]T[/bold red])itle Search")
    print("\n")
    print("\t([bold red]U[/bold red])pdate the Project Gutenberg Catalog")
    print("\t([bold red]M[/bold red])ain Menu\n")
    choice = input("What would you like to do? ")

    if choice.lower() == 'a':
        search_for_author(df)
    elif choice.lower() == 't':
        search_for_title(df)
    elif choice.lower() == 's':
        search_for_subject(df)
    elif choice.lower() == 'u':
        update_the_catalog()
    elif choice.lower() == 'm':
        return    
    else:
        search_menu()

