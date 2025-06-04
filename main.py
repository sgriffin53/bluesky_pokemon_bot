import sys
import aiohttp, asyncio
import json, mysql.connector
import random
import requests
from atproto import Client, client_utils
import time
class Listing:
    def __init__(self):
        self.title = ''
        self.set = None
        self.link = None
        self.price = None
        self.valuation = None
        self.price_gbp = None
        self.seller_info = None
        self.identified_as = None
        self.price_diff_percent = None
        self.price_diff_raw = None
        self.postage = None
        self.auction_type = None
        self.total_price = None
        self.region = None
        self.grade = None
        self.end_date = None
        self.seller_country = None

def get_classic_cards():
    f = open('classic.txt', 'r',encoding='utf-8')
    lines = f.readlines()
    f.close()
    classic_cards = []
    for line in lines:
        parts = line.split('[')
        if len(parts) < 2:
            continue  # skip if no set name

        # The part before the '[' contains the card name
        before_bracket = parts[0].strip()
        card_name = ' '.join(before_bracket.split()[1:])  # skip the number at the beginning
        number = line.split("/")[0]
        # The part inside the brackets is the set name
        set_name = parts[1].split(']')[0].strip()

        #print(f"Card Name: {card_name}, Set Name: {set_name}, Number: {number}")
        classic_cards.append((number, card_name, set_name))
    return classic_cards

def get_values_from_db(region):
    with open('sql_login.json', 'r') as config_file:
        config = json.load(config_file)

    connection = mysql.connector.connect(
        host=config['host'],
        user=config['user'],
        password=config['password'],
        database=config['database'],
        auth_plugin=config['auth_plugin']  # Specify the authentication plugin
    )

    cursor = connection.cursor()
    # Define the query
    query = '''SELECT * FROM listings WHERE region = 'US' AND valuation >= 30 AND grade = 'Ungraded' AND auction_type = 'Buy it now' AND price_diff_percent > 80 AND price_diff_percent < 600
            AND title NOT LIKE '%HP%' AND title NOT LIKE '%DMG%'
            '''
    if region == 'UK':
        query = '''SELECT * FROM listings WHERE region = 'UK' AND valuation >= 30 AND grade = 'Ungraded' AND auction_type = 'Buy it now' AND price_diff_percent > 80 AND price_diff_percent < 600
                AND title NOT LIKE '%HP%' AND title NOT LIKE '%DMG%'
                '''

    # Execute the query with parameters
    cursor.execute(query)

    listings = []
    # Fetch all results
    results = cursor.fetchall()
    listings_cards_just_cards = []
    print(len(results))
    classic_cards = get_classic_cards()
    f = open('already_posted.txt', 'r', encoding='utf-8')
    lines = f.readlines()
    f.close()
    already_posted = []
    for line in lines:
        line = line.replace("\n","")
        already_posted.append(line)
    for row in results:
        title = row[1]
        set_name = row[2]
        price = row[13]
        valuation = row[3]
        image = row[5]
        link = row[7]
        if link in already_posted:
            continue
        identified_as = row[11]
        price_diff_percent = row[10]
        banned_words = ['italian', 'poor' , 'read', 'booster' , 'played', 'world series', 'world champion', 'damage', ' lot', '25th', 'gym challenge', 'gym heroes', 'heavy play' 'celebratio']
        skip = False
        for word in banned_words:
            if word in title.lower(): skip = True
        if "ITA" in title: continue
        if skip: continue
        if 'booster' in identified_as.lower(): continue
        if 'elite' in identified_as.lower(): continue
        if "[" in identified_as:
            if "holo]" not in identified_as.lower(): continue
        result_number = '#99999999999'
        for word in identified_as.split(" "):
            if '#' in word:
                result_number = word.replace("#","")
        skip = False
        for card in classic_cards:
            card_number = card[0]
            card_name = card[1]
            card_set_name = card[2]
            if card_set_name.lower() == set_name.lower():
                if card_number == result_number:
                    skip = True
        if skip: continue
        listing = Listing()
        listing.title = title
        listing.valuation = valuation
        listing.price = price
        listing.identified_as = identified_as
        listing.set_name = set_name
        listing.link = link
        listing.image = image
        listings.append(listing)
    print(len(listings))
    return listings

def make_post(listing, region):
    download_image(listing.image.replace("140", "1600"), 'temp_image.jpg')
    f = open('temp_image.jpg', 'rb')
    image_data = f.read()
    f.close()
    orig_link = listing.link
    set_name = listing.set_name
    set_name = set_name.title().replace("'S", "'s")
    listing.link += '?campid=5339084796&toolid=10001&mkevt=1'
    identified_as = listing.identified_as
    percent_off = (100 - (listing.price * 100 / listing.valuation))
    currency_sign = '$'
    usd_gbp = 0.74
    if region == 'UK':
        currency_sign = '£'
        listing.price *= usd_gbp
        listing.valuation *= usd_gbp
    listing.price = round(listing.price, 2)
    listing.valuation = round(listing.valuation, 2)
    PC_url = 'https://www.pricecharting.com/game/pokemon-' + set_name.replace(" ","-").lower() + "/" + identified_as.replace(" ", "-").replace("#", "").lower()
    text_builder = client_utils.TextBuilder()
    text_builder.text(set_name + " " + identified_as + " deal\n")
    text_builder.text(f"Listed for " + currency_sign + str(listing.price) + f" (Valued at " + currency_sign + str(listing.valuation) + ")\n")
    text_builder.text("Ebay: ")
    text_builder.link(listing.title[:80], listing.link)
    text_builder.text("\nValue info: ")
    text_builder.link("Pricecharting", PC_url)
    text_builder.text("\n" + str(int(percent_off)) + "% off! #PokemonTCG #DealFinder #TCGdeals\n")
    text_builder.link("More deals at Jimmy's TCG Deal Finder", 'https://www.jimmyrustles.com/pokemondeals')
    post_text = text_builder
    print("len:", len(str(post_text)))
    file = 'bluesky_password.txt'
    if region == 'UK': file = 'bluesky_password_uk.txt'
    f = open(file, 'r',encoding='utf-8')
    lines = f.readlines()
    f.close()
    bsky_password = lines[0].replace("\n","")
    client = Client()
    username = 'PokemonDealsBot.bsky.social'
    if region == 'UK': username = 'PokemonDealsBotUK.bsky.social'
    client.login(username, bsky_password)
    client.send_image(text=post_text, image=image_data, image_alt=listing.set_name + " " + listing.identified_as)
    f = open('already_posted.txt','a')
    f.write(orig_link + "\n")
    f.close()

def get_card_to_post(listings):
    listing = random.choice(listings)
    set_name = listing.set_name
    identified_as = listing.identified_as
    PC_url = 'https://www.pricecharting.com/game/pokemon-' + set_name.replace(" ", "-").lower() + "/" + identified_as.replace(" ", "-").replace("#", "").lower()
    print("-----")
    print("Title:", listing.title)
    print("Pricecharting URL:", PC_url)
    print("Price:", listing.price)
    print("Valuation:", listing.valuation)
    print("Link:", listing.link)
    return listing

def download_image(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"✅ Image saved as {filename}")
    else:
        print(f"❌ Failed to download image. Status code: {response.status_code}")

def main():
    while True:
        print("Making UK Post")
        listings = get_values_from_db('UK')
        listing = get_card_to_post(listings)
        make_post(listing, 'UK')
        print("Making US Post")
        listings = get_values_from_db('US')
        listing = get_card_to_post(listings)
        make_post(listing, 'US')
        print("Sleeping for an hour")
        time.sleep(60 * 60)

main()