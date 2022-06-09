import os
import pandas as pd
import requests
from os.path import exists
from rich import print
from rich.console import Console
from rich.table import Table

console = Console()
list_of_files = os.listdir('input')

def check_file_exists():
    if not exists('meta/pg_catalog.csv'):
        choice = input("Looks like we don't have the Project Gutenberg catalog. Would you like to download it now? (y/n) ")
        if choice.lower() == 'y':
            url = f'https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv'

            r = requests.get(url, allow_redirects=False)
            open(f'meta/pg_catalog.csv', 'wb').write(r.content)
        elif choice.lower() == 'n':
            return
        else:
            check_file_exists()
    df = pd.read_csv('meta/pg_catalog.csv', low_memory=False)
    return df


def display_results_table(results, type_search):
    list_of_ids = []
    table = Table(title=f"Results", min_width=60, style="purple", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Author", justify="left", style="magenta")
    table.add_column("Title", justify="left", style="green")

    for index, row in results.iterrows():
        table.add_row(str(row['Text#']), row['Authors'], row['Title'])
        list_of_ids.append(str(row['Text#']))
    
    console.print(table)
    get_selection_by_id(type_search, list_of_ids)

def get_name_for_file():
    choice = input("\nWhat should I call this file? (Note: I just need the name, it will be a .html file by default) Or press enter to cancel. ")
    test_choice = choice + ".html"
    if test_choice == ".html":
        return
    elif test_choice in list_of_files:
        print("Sorry, that name is already taken.")
        get_name_for_file()
    else:
        return choice

def get_selection_by_id(type_search, list_of_ids):
    choice = input("Which book would you like? Or just hit enter to select none of these: ")
    if choice in list_of_ids:
        filename = get_name_for_file()
        if filename == None:
            search_menu()
        else:
            download_book_by_id(choice, filename)
    elif choice == "":
        search_menu()
    else:
        print("Sorry, that's not one of the choices.\n")
        get_selection_by_id(type_search, list_of_ids)
        

def download_book_by_id(book_id, filename):
    #Sample Format for HTML File: https://www.gutenberg.org/files/1000/1000-h/1000-h.htm
    url = f'https://www.gutenberg.org/files/{book_id}/{book_id}-h/{book_id}-h.htm'

    r = requests.get(url, allow_redirects=False)
    if r.status_code == 404:
        print("\nSorry, I can't find an HTML version of that text.")
        input("Press enter to continue...\n")
    if r.status_code == 200:
        open(f'input/{filename}.html', 'wb').write(r.content)

def search_for_author(df):
    author_choice = input("What author would you like to find? Or press enter to go back. ")
    if author_choice == "":
        search_menu()
    else:
        author_results = df.loc[(df['Authors'].str.contains(author_choice, na=False, case=False) & (df['Type']=="Text"))]

        display_results_table(author_results, "author")

def search_for_title(df):
    title_choice = input("What book would you like to find? Or press enter to go back. ")
    if title_choice == "":
        search_menu()
    else:
        title_results = df[(df['Title'].str.contains(title_choice, na=False, case=False) & (df['Type']=="Text"))]

        display_results_table(title_results, "title")

def search_menu():
    console.clear()
    df = check_file_exists()

    print("\n\n")
    print("\t([bold red]A[/bold red])uthor Search")
    print("\t([bold red]T[/bold red])itle Search")
    print("\n")
    print("\t([bold red]M[/bold red])ain Menu\n")
    choice = input("What would you like to do? ")

    if choice.lower() == 'a':
        search_for_author(df)
    elif choice.lower() == 't':
        search_for_title(df)
    elif choice.lower() == 'm':
        return    
    else:
        search_menu()

