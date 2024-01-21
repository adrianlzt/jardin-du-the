#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#

"""
Generate a google sheet with the list of teas and their ingredients given a list of URLs.

To be able to create a google sheet, you need to create a google service account and download the credentials file.
Then you need to share the google sheet with the email of the service account.
"""

import os
import sys
import json

import pygsheets
import requests
from lxml import html
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4-1106-preview"
# MODEL = "gpt-3.5-turbo-16k"


def extract_teas(file_urls):
    """Given a list of URLs (file urls.txt), extract the content of the web pages and save it as a json file (tea_orig_data)"""

    # Define the XPATHs to extract
    xpaths = {
            "short_description": "//*[@class='woocommerce-product-details__short-description']/p",
            "description": "//*[@id=\"tab-description\"]/p",
            "ingredients": "//*[@id=\"tab-ingredients\"]/p",
    }

    # Open the file with the list of URLs
    with open(file_urls, "r") as f:
        urls = f.read().splitlines()

    # Create an empty list to store the results
    results = []

    # Loop through each URL
    for url in urls:
        # Get the web page content
        response = requests.get(url)
        # Parse the HTML tree
        tree = html.fromstring(response.content)
        # Get the web page title
        title = tree.findtext(".//title")
        # Remove from the title the last " - Jardin du thé"
        title = title.replace(" - Jardin du thé", "")

        # Create a dictionary to store the extracted content
        content = {
                "title": title,
                "url": url,
        }
        # Loop through each XPATH
        for key,xpath in xpaths.items():
            # Get the text content of the element
            text = tree.xpath(xpath + "/text()")
            if text == []:
                text = tree.xpath(xpath + "/*/text()")

            # Join the text content into a single string
            text = " ".join(text)
            # Remove new lines and tabs
            text = text.replace("\n", "")
            text = text.replace("\t", "")

            # Add the text content to the dictionary with the XPATH as the key
            content[key] = text

        # Get the img URL from the "img" with class "wp-post-image"
        img = tree.xpath("//*[@class='wp-post-image']/@src")
        # Add the img URL to the dictionary
        content["img"] = img[0]

        # Append the dictionary to the results list
        results.append(content)

    return results


def extract_ingredients(tea_data):
    """Extract ingredients from each tea

    Given a list of teas (tea_data), create a prompt to extract ingredients from each tea using OpenAI's API.
    The ingredients should be normalized, for example, "morceaux de gingembre" should be returned as "gingembre".
    Save the results as a json file (tea_extended_data.json).
    """

    # Create a prompt to extract ingredients from each tea
    prompt = """Extract ingredients given a description of a tea.
    The ingredients should be normalized, for example, "morceaux de gingembre" should be returned as "gingembre".
    'The vert' should not be considered as an ingredient.

    Example:

    PROMPT: Thé vert Ginger pepper. Gingembre et poivre noir. Thé vert parfumé au gingembre. Agrémenté de morceaux de gingembre et de poivre noir. thé vert (90 %), morceaux de gingembre, grains de poivre noir, arôme
    REPONSE: gingembre, poivre noir


    TEA TEXT: {tea_text}
    """

    for tea in tea_data:
        p = prompt.format(tea_text=".".join([tea["title"], tea["short_description"], tea["description"], tea["ingredients"]]))

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "user",
                    "content": p,
                },
            ],
        )

        # Save list of ingredients as a list, removing whitespaces
        tea["list_of_ingredients"] = [ingredient.strip() for ingredient in response.choices[0].message.content.split(",")]

    return tea_data


def generate_google_sheet(tea_extended_data, sheet_title):
    """Given a list of teas (tea_extended_data), generate a Google Sheet.

    The list contains a list of teas with its ingredients (list_of_ingredients key).
    First, all ingredients are extracted from the list of teas.
    Then, a Google Sheet is generated with one column for each ingredient and one row for each tea.
    The ingredients should be binary, 1 if the ingredient is present in the tea, 0 otherwise.
    Also, the Google Sheet should contain a column with the name of the tea, url, image url and "description" where the fields "short_description", "description" and "ingredients" are concatenated.

    Example, for a given this data:
        {
            "title": "Thé vert Ginger pepper",
            "url": "https://jardin-du-the.com/produit/ginger-pepper/",
            "short_description": "Gingembre et poivre noir",
            "description": "Thé vert parfumé au gingembre. Agrémenté de morceaux de gingembre et de poivre noir",
            "ingredients": "thé vert (90 %), morceaux de gingembre, grains de poivre noir, arôme",
            "img": "https://jardin-du-the.com/wp-content/uploads/2023/06/The_vert_ginger_pepper-600x600.png",
            "list_of_ingredients": ["gingembre", "poivre noir"]
        }

    The Google Sheet should be:
        title,url,img,description,gingembre,poivre noir
        Thé vert Ginger pepper,https://jardin-du-the.com/produit/ginger-pepper/,https://jardin-du-the.com/wp-content/uploads/2023/06/The_vert_ginger_pepper-600x600.png,Gingembre et poivre noir,Thé vert parfumé au gingembre. Agrémenté de morceaux de gingembre et de poivre noir,1,1
    """
    # Create a list with all ingredients
    ingredients = []
    for tea in tea_extended_data:
        ingredients.extend(tea["list_of_ingredients"])
    # Lower case
    ingredients = [ingredient.lower() for ingredient in ingredients]
    # Change "’" to "'"
    ingredients = [ingredient.replace("’", "'") for ingredient in ingredients]
    # Remove prefix "chips de" or "chips d'"
    ingredients = [ingredient.replace("chips de ", "") for ingredient in ingredients]
    ingredients = [ingredient.replace("chips d'", "") for ingredient in ingredients]
    # Remove suffix " grillé", " râpée"
    ingredients = [ingredient.replace(" grillé", "") for ingredient in ingredients]
    ingredients = [ingredient.replace(" râpée", "") for ingredient in ingredients]
    # Remove "écorce d'", "écorce de", "écorces d'", "écorces de"
    ingredients = [ingredient.replace("écorce d'", "") for ingredient in ingredients]
    ingredients = [ingredient.replace("écorce de", "") for ingredient in ingredients]
    ingredients = [ingredient.replace("écorces d'", "") for ingredient in ingredients]
    ingredients = [ingredient.replace("écorces de", "") for ingredient in ingredients]
    # Remove "tranches d'", "tranches de"
    ingredients = [ingredient.replace("tranches d'", "") for ingredient in ingredients]
    ingredients = [ingredient.replace("tranches de", "") for ingredient in ingredients]
    # Remove "morceaux d'", "morceaux de"
    ingredients = [ingredient.replace("morceaux d'", "") for ingredient in ingredients]
    ingredients = [ingredient.replace("morceaux de", "") for ingredient in ingredients]
    # Replace "menthe poivrée" and "menthe verte" by "menthe"
    ingredients = [ingredient.replace("menthe poivrée", "menthe") for ingredient in ingredients]
    ingredients = [ingredient.replace("menthe verte", "menthe") for ingredient in ingredients]
    # Replace "poivre noir" and "poivre blanc", "poivre rose" by "poivre"
    ingredients = [ingredient.replace("poivre noir", "poivre") for ingredient in ingredients]
    ingredients = [ingredient.replace("poivre blanc", "poivre") for ingredient in ingredients]
    ingredients = [ingredient.replace("poivre rose", "poivre") for ingredient in ingredients]
    # Replace "citron caviar" and "citron vert" by "citron"
    ingredients = [ingredient.replace("citron caviar", "citron") for ingredient in ingredients]
    ingredients = [ingredient.replace("citron vert", "citron") for ingredient in ingredients]
    # Replace "clous de girofle" by "clou de girofle"
    ingredients = [ingredient.replace("clous de girofle", "clou de girofle") for ingredient in ingredients]
    # Replace "figue de barbarie" by "figue"
    ingredients = [ingredient.replace("figue de barbarie", "figue") for ingredient in ingredients]
    # Remove accents from the first letter (to sort alphabetically)
    ingredients = [ingredient.replace("é", "e") for ingredient in ingredients]
    ingredients = [ingredient.replace("è", "e") for ingredient in ingredients]
    ingredients = [ingredient.replace("à", "a") for ingredient in ingredients]
    ingredients = [ingredient.replace("â", "a") for ingredient in ingredients]
    ingredients = [ingredient.replace("ê", "e") for ingredient in ingredients]
    ingredients = [ingredient.replace("î", "i") for ingredient in ingredients]
    ingredients = [ingredient.replace("ô", "o") for ingredient in ingredients]
    ingredients = [ingredient.replace("û", "u") for ingredient in ingredients]
    ingredients = [ingredient.replace("ç", "c") for ingredient in ingredients]
    # Remove ingredients with more than 50 characters (errors by the llm)
    ingredients = [ingredient for ingredient in ingredients if len(ingredient) < 50]
    # Remove duplicates
    ingredients = list(set(ingredients))
    # Sort alphabetically
    ingredients.sort()

    # Create a Google Sheet
    gc = pygsheets.authorize(service_file="google-sa.json")
    # Create a new sheet
    sh = gc.open("Jardin du the")

    # Check if a sheet with the same name already exists
    for sheet in sh:
        if sheet.title == sheet_title:
            # warn and exit
            print("A sheet with the same name already exists")
            return

    # Create a new sheet
    wks = sh.add_worksheet(sheet_title, rows=len(tea_extended_data) + 1, cols=len(ingredients) + 4)

    # Set the title
    wks.title = sheet_title
    # Set the header
    wks.update_value("A1", "title")
    wks.update_value("B1", "img")
    wks.update_value("C1", "description")
    # Set the ingredients
    for i, ingredient in enumerate(ingredients):
        wks.update_value((1,i+4), ingredient)

    # Set the data
    for i, tea in enumerate(tea_extended_data):
        # Write the title, should be a link to the url
        wks.update_value("A" + str(i + 2), "=HYPERLINK(\"" + tea["url"] + "\"; \"" + tea["title"] + "\")")
        wks.update_value("B" + str(i + 2), "=IMAGE(\"" + tea["img"] + "\")")

        # Write the description
        full_description = tea["short_description"] + ". " + tea["description"] + ". " + tea["ingredients"]
        wks.update_value("C" + str(i + 2), full_description)
        # Set the wrap to true
        cell = wks.cell("C" + str(i + 2))
        cell.wrap_strategy = "WRAP"

        # Write the ingredients
        for j, ingredient in enumerate(ingredients):
            if ingredient.lower() in tea["list_of_ingredients"]:
                wks.update_value((i + 2, j + 4), 1)
            else:
                wks.update_value((i + 2, j + 4), 0)


    # Autoadjust the column width in column A
    wks.adjust_column_width(start=1, end=1)
    # Set column B and C width to 300px
    wks.adjust_column_width(start=2, end=3, pixel_size=300)
    # Autoadjust the rest of the columns
    wks.adjust_column_width(start=4, end=len(ingredients) + 3)
    # Set all rows but the first one to 300px
    wks.adjust_row_height(start=2, end=len(tea_extended_data) + 1, pixel_size=300)


def main(file_with_urls, name):
    """Main function

    Get a file path with a list of links and a name to use as the title
    for the Google Sheet.
    """

    # Skip the extraction of the teas if already done
    tea_orig_data_filename = f"{name}-initial-data.json"
    if os.path.isfile(tea_orig_data_filename):
        with open(tea_orig_data_filename, "r") as f:
            tea_orig_data = json.load(f)
    else:
        print("Extracting teas...")
        tea_orig_data = extract_teas(file_with_urls)
        # Save the results list as a json file
        with open(tea_orig_data_filename, "w") as f:
            f.write(json.dumps(tea_orig_data, indent=4, ensure_ascii=False))

    # Skip the extraction of the ingredients if already done
    tea_extended_data_filename = f"{name}-extended-data.json"
    if os.path.isfile(tea_extended_data_filename):
        with open(tea_extended_data_filename, "r") as f:
            tea_extended_data = json.load(f)
    else:
        print("Extracting ingredients...")
        tea_extended_data = extract_ingredients(tea_orig_data)
        with open(tea_extended_data_filename, "w") as f:
            f.write(json.dumps(tea_extended_data, indent=4, ensure_ascii=False))

    # Generate a Google Sheet document with the data
    print("Generating Google Sheet document...")
    generate_google_sheet(tea_extended_data, name)

if __name__ == "__main__":
    # Get the first argument as the file with the URLs
    if len(sys.argv) != 3:
        print("Usage: python3 " + sys.argv[0] + " <file_with_urls>", "<name>")
        sys.exit(1)

    file_with_urls = sys.argv[1]
    name = sys.argv[2]

    main(file_with_urls, name)
