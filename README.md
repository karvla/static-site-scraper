# Static Site Scraper
Downloads a website for local use.

## Install dependencies
Install dependencies using poetry:

`poetry install` then activate the virtual environment using `poetry shell`

You can also use pip to install the dependencies:

`pip3 install -f requirements.txt`

## Run the program
Execute the script by running `python3 static_site_scraper.py URL OUTPUT-FOLDER`. 

For example: `python3 static_site_scraper.py https://books.toscrape.com books`

## About the design
The program uses recursion to crawl a website and downloading all documents that are linked. The program will not download pages that are hosted on other domains than the one it started out on. The script can either be used via the CLI or as a module by importing and calling the `get_site` function. The function returns a dict with URLs as keys and documents and values and a set containing all URL that points to assets such as images or videos. When using the CLI the non-text assets will be downloaded after all documents have been downloaded.

There are currently some limitations
* The script will not convert absolute paths relative paths in the html. This means that some links in the downloaded web page won't work.
* Currently, the pages are downloaded using depth first. This not very good if you only want to download a part of a large site suing the `--page-limit` option since most of the links in the first page won't work.
