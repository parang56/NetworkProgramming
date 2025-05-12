import requests
from bs4 import BeautifulSoup
import csv
import re


def get_wikipedia_url():
    while True:
        url = input("Wikipedia URL: ")
        if validate_wikipedia_url(url):
            return url
        else:
            print("Invalid Wikipedia URL. Please try again.")


def validate_wikipedia_url(url):
    pattern = re.compile(r"^https?://(en\.)?wikipedia\.org/wiki/.+$")
    return bool(pattern.match(url))


def scrape_wikipedia_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    title = soup.find('h1', {'id': 'firstHeading'}).text
    paragraphs = soup.find_all('p')
    first_paragraph = ""

    for paragraph in paragraphs:
        if paragraph.text.strip():
            first_paragraph = paragraph.text.strip()
            break

    return title, first_paragraph


def save_to_csv(data):
    with open('Wikipedia_Content.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Title', 'First Paragraph'])
        writer.writerow(data)


def main():
    url = get_wikipedia_url()
    title, first_paragraph = scrape_wikipedia_page(url)

    print(f"Title: {title}")
    print(f"Description: {first_paragraph}")

    save_to_csv((title, first_paragraph))


if __name__ == "__main__":
    main()
