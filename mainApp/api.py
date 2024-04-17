import math
import datetime
import httpx
import redis
import json
from selectolax.parser import HTMLParser
from mainApp.visibleConstell import VisibleConstell
from decimal import Decimal, getcontext
from pymongo import MongoClient
from redis.exceptions import RedisError

def calculate_JD(time_n_date):
    """
    Calculate the Julian Date (JD) from the UT date and time.

    Args:
        time_n_date (dict): A dictionary containing the year, month, day, hour, minute, and second.

    Returns:
        Decimal: The calculated Julian Date (JD).
    """
    getcontext().prec=10
    year =   int(time_n_date['year'])
    month =  int(time_n_date['month'])
    day =    int(time_n_date['day'])
    hour =   int(time_n_date['hour'])
    minute = int(time_n_date['minute'])
    second = int(time_n_date['second'])

    return Decimal(str(367 * year - 7 * (year + (month + 9)\
                                        // 12) // 4 + 275 * month\
                                              // 9 + day + 1721013.5 + \
                                                (hour + minute / 60 + second / 3600) / 24))

def calculate_GMST_alt(time, date):
    getcontext().prec=10
    time_l = time.split(":")
    date_l = date.split("-")
    time_n_date = {
        'year':     date_l[0],
        'month':    date_l[1],
        'day':      date_l[2],

        'hour':     time_l[0],
        'minute':   time_l[1],
        'second':   time_l[2],
    }

    JD = calculate_JD(time_n_date)


    midnight = Decimal((math.floor(JD) + Decimal((0.5))))
    days_since_midnight = Decimal((JD - midnight))
    hours_since_midnight = Decimal((days_since_midnight * Decimal((24 ))))
    days_since_epoch = Decimal((JD - Decimal((2451545.0))))
    centuries_since_epoch = Decimal((days_since_epoch / Decimal((36525))))
    whole_days_since_epoch = Decimal((midnight - Decimal((2451545.0))))



    GMST = Decimal(str(6.697374558)) \
    + Decimal(str(0.06570982441908)) * whole_days_since_epoch \
    + Decimal(str(1.00273790935)) * hours_since_midnight \
    + Decimal(str(0.000026)) * centuries_since_epoch**Decimal(str(2))


    GMST_hours = math.trunc(GMST) % 24 
    GMST_minutes =  round((GMST - math.trunc(GMST)) * 60 , 2 )
    GMST_seconds =  math.trunc(round((GMST_minutes - math.trunc(GMST_minutes)) , 2)*60)
    GMST_minutes = math.floor(GMST_minutes)

    GMST = GMST_hours + GMST_minutes/Decimal(60) + GMST_seconds/Decimal(3600)

    #print(f'GMST is : {GMST_hours}:{GMST_minutes}:{GMST_seconds}\n')

    return GMST

def calculate_lst(gmst, long):
    """
    Calculate the Local Sidereal Time (LST) based on the Greenwich Mean Sidereal Time (GMST) and longitude.

    Args:
        gmst (Decimal): The Greenwich Mean Sidereal Time.
        long (Decimal): The longitude of the location.

    Returns:
        Decimal: The Local Sidereal Time (LST) in hours.
    """
    # Convert longitude to hours
    long_hours = long / Decimal(15)

    # Calculate LST
    lst = gmst + long_hours

    # Make sure LST is in the range 0-24
    lst = lst % Decimal(str(24))

    return lst

def equatorial_to_horizontal(ra, dec, lat, lst): 
    """
    Convert equatorial coordinates (right ascension and declination) to horizontal coordinates (azimuth and altitude).

    Args:
        ra (Decimal): The right ascension in degrees.
        dec (Decimal): The declination in degrees.
        lat (Decimal): The latitude of the location in degrees.
        lst (Decimal): The Local Sidereal Time (LST) in hours.

    Returns:
        tuple: A tuple containing the azimuth and altitude in degrees.
    """
   
    # Convert angles from degrees to radians
    ra = math.radians(ra*15)
    dec = math.radians(dec)
    lat = math.radians(lat)
    lst = math.radians(lst*15)

    HourAngle = lst - ra
    HourAngle = (HourAngle + math.pi) % (2 * math.pi) - math.pi

    alt = math.asin(math.sin(dec) * math.sin(lat) + math.cos(dec) * math.cos(lat) * math.cos(HourAngle))
    az = math.acos((math.sin(dec) - math.sin(lat) * math.sin(alt)) / (math.cos(lat) * math.cos(alt)))

    if math.sin(HourAngle) > 0:
        az = 2 * math.pi - az

    alt = math.degrees(alt)
    az = math.degrees(az)
    return az, alt

def connect_to_db():
    """
    Connect to the database and retrieve the collection of constellations.

    Returns:
        pymongo.collection.Collection: The collection of constellations from the database.
    """
    client = MongoClient('mongodb://localhost:27017')
    db = client['stargazeNow']
    return db['constellations']

def connect_to_redis():
    """
    Connects to a Redis server running on localhost at port 6379.

    Returns:
        Redis: A Redis client object for interacting with the Redis server.
    """
    try:
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        r.ping()
    except redis.ConnectionError:
        r = None
        print("Unable to reach Redis, working with MongoDB exclusively.")
    return r

def are_visible_many(lat, lst, constells):
    """
    Check which constellations are visible at a specific location and time.

    Args:
        lat (Decimal): The latitude of the location.
        lst (Decimal): The Local Sidereal Time (LST) at the location.
        constells (list): List of constellations to check for visibility.

    Returns:
        list: A list of visible constellations with their horizontal coordinates.
    """
    visible = []
    for elem in constells:
        ra = Decimal(elem['ra'])
        dec = Decimal(elem['dec'])
        az, alt = equatorial_to_horizontal(ra, dec, lat, lst)
        if az > 0 and alt > 0:
            new_visible_constell = VisibleConstell(elem, round(az, 3), round(alt, 3))
            visible.append(new_visible_constell)
    return visible

def get_utc_time(long, time):
    """
    Get the UTC time based on the longitude and local time.

    Args:
        long (str): The longitude of the location.
        time (str): The local time to adjust.

    Returns:
        str: UTC time calculated using longtitude of location and local time.
    """
    hours = Decimal(time[:2])
    long_hours = Decimal(long) // Decimal(15)
    hours = str(abs((hours - long_hours)%24)).rjust(2,'0')
    min_sec = time[2:]
    return hours + min_sec

def fix_long_lat(long, lat):
    """
    Fix the format of longitude and latitude values.

    Args:
        long (str): The longitude value to be formatted.
        lat (str): The latitude value to be formatted.

    Returns:
        tuple (Decimal, Decimal): A tuple containing the fixed longitude and latitude values.

    Examples:
        >>> long = 147.3058, lat = 60.95
        <<< fix_long_lat(long, lat):
        60.950000, 147.305800
    """
    whole, dec = long.split('.')
    dec = dec.ljust(6,'0')
    long = Decimal(f"{whole}.{dec}")
    whole, dec = lat.split('.')
    dec = dec.ljust(6,'0')
    lat = Decimal(f"{whole}.{dec}")
    return long, lat

def get_visible_constells(long, lat, time, date):
    """
    Get visible constellations at a specific location and time.

    Args:
        long (float): The longitude of the location.
        lat (float): The latitude of the location.
        time (str): The local time at the location.
        date (str): The date for which to calculate the visible constellations.

    Returns:
        tuple: Tuple containing list with visible constellations and a dictionary with observational information.
    """
    getcontext().prec=10
    long, lat = fix_long_lat(long, lat)

    utc_time = get_utc_time(long, time)
    gmst = calculate_GMST_alt(utc_time, date)
    lst = calculate_lst(gmst, long)
    constells = get_constells()
    visible = are_visible_many(lat, lst, constells)

    observ_info = {
        'Longtitude': long, 
        'Latitude': lat, 
        'Local_Time': time, 
        'UTC_Time': utc_time, 
        'Date': date
    }
    return visible, observ_info

def get_constell_by_id_db(constell_id):
    constell = connect_to_db().find_one({'constell_id': constell_id})
    if constell is not None:
        constell["_id"] = str(constell.get("_id"))
    return constell

def get_constell_by_id(constell_id):
    """
    Retrieves constellation object from DB or Redis.

    Args:
        constell_id (float): The float id of constell_id field of an object from DB.

    Returns:
        (dict): The constell object in dictionary form with _id as a string.
    """
    # Connect to Redis
    redis_coll = connect_to_redis()
    if redis_coll is None:
        return get_constell_by_id_db(constell_id)
    #Check if key-value pair exists in Redis
    constell = redis_coll.zrangebyscore("constellations", constell_id, constell_id)
    if len(constell) > 0:
        # If pair exist, reset it expiration time and return cached object
        constell = json.loads(constell[0])
    else:
        # If pair does not exist, try to retrieve it from DB
        constell = get_constell_by_id_db(constell_id)
        # And place it in Redis' collection
        redis_coll.zadd("constellations", {json.dumps(constell): constell_id})
    redis_coll.expire("constellations", 20)
    return constell
        

def get_constells():
    """
    Retrieves a list of constellations from the database after connecting to Redis.

    Returns:
        list: A list of dictionaries representing constellations with modified keys.
    """
    # Connect to Redis
    redis_coll = connect_to_redis()
    scores = []
    cached_values = []
    redis_cached = None
    if redis_coll is not None:
        redis_cached = redis_coll.zrange("constellations",0, -1, withscores=True )
        if  redis_cached:
            cached_values, scores = map(list, zip(*redis_cached))
            cached_values = [json.loads(value) for value in cached_values]
            redis_coll.expire("constellations", 20)

    # retrieve all non-cached constells
    constell_db_list = list(connect_to_db().find({'constell_id': {'$nin': scores}}))

    if constell_db_list:
    # convert ObjectId to str and cache all uncached elements
        to_cache = {}
        for elem in constell_db_list:
            elem["_id"] = str(elem["_id"])
            to_cache[json.dumps(elem)] = elem["constell_id"]
        
        if redis_coll is not None:
            redis_coll.zadd("constellations", to_cache)

    sorted_list = constell_db_list + cached_values

    # we'll sort only if there were cached constellations
    if  redis_cached:
        sorted_list = sorted(sorted_list, key=lambda elem: elem["constell_id"])
    return sorted_list
    
def get_time_date():
    """
    Get the current date and time.
    Returns:
        tuple: A tuple containing the current date and time in 'YYYY-MM-DD' and 'HH:MM:SS' format.
    """
    d_t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    d,t = d_t.split(' ')
    return d,t

def get_html_wiki_page(page_title):
    """
    Retrieves html content of a Wikipedia page.

    Args:
        page_title (str): The title of the Wikipedia page.

    Returns:
        str: The content of the Wikipedia page.

    Examples:
        >>> page_title = "Orion_(constellation)"
        <<< get_wikipedia_page(page_title):
        '<div class="mw-parser-output">\n<p>Orion is a prominent constellation located on the celestial equator and visible throughout the world.</p>\n<p>...</p>\n</div>'
    """
    # Make the GET request to the MediaWiki API
    response = httpx.get(page_title)
    # Parse the JSON response
    data = response.json()
    return data['parse']['text']['*']

def retreive_from_redis(key):
    """
    Retrieves a value from Redis associated with the specified key and sets a 20-second expiration if the value exists.

    Args:
        key (str): The key used to retrieve the value from Redis.

    Returns:
        str: The value associated with the key in Redis, or None if the key does not exist.
    """
    value = None
    redis_coll = connect_to_redis()
    if redis_coll is not None:
        value = redis_coll.get(key)
        if value is not None:
            redis_coll.expire(key, 20)
    return value

def cache_in_redis(key, value):
    """
    Caches a value in Redis with the specified key for a duration of 20 seconds.

    Args:
        key (str): The key under which the value will be cached in Redis.
        value (str): The value to be cached in Redis.

    Returns:
        None
    """
    redis_coll = connect_to_redis()
    if redis_coll is not None:
        redis_coll.psetex(key, 20000, value)

def get_wiki_cached(page_url, suffix):
    """
    Retrieves a cached JSON object associated with the suffix from Redis. If not cached, scrapes the specified Wikipedia page,
    caches the scraped data in Redis, and returns the scraped data.

    Args:
        page_url (str): The URL of the Wikipedia page to scrape.
        suffix (str): The suffix used as the key for caching and retrieving data from Redis.

    Returns:
        dict: A JSON object representing the scraped data from the Wikipedia page.
    """
    cached = retreive_from_redis(suffix)
    if cached is not None:
        return json.loads(cached)
    
    scraped = scrape_wiki_page(page_url)
    cache_in_redis(suffix, json.dumps(scraped))
    return scraped
        

def scrape_wiki_page(page_url):
    """
    Scrapes information from a Wikipedia page.

    Args:
        page_url (str): The URL of the Wikipedia page.

    Returns:
        dict: A dictionary containing the scraped information.
            - 'shortdesc' (str): The short description of the page.
            - 'symbolism' (str): The symbolism associated with the page.
            - 'neighbours' (str): The neighboring elements as an unordered list.
            - 'visibility' (str): The visibility of the page.

    Examples:
        >>> page_url = "https://en.wikipedia.org/wiki/Orion_(constellation)"
        >>> scrape_wiki_page(page_url)
        {
            'shortdesc': 'Orion is a prominent constellation located on the celestial equator and visible throughout the world.',
            'symbolism': 'Orion is named after a hunter in Greek mythology.',
            'neighbours': '<ul> <li> Taurus <br /> <li> Eridanus <br /> <li> Lepus <br />',
            'visibility': 'Orion is visible in both the northern and southern hemispheres.'
        }
    """
    page = get_html_wiki_page(page_url)
    # create as parsing tree
    parsed = HTMLParser(page)
    # retrieve short description from tree by searching a div with class="shortdescription
    short_desc = parsed.css_first("div.shortdescription").text()

    # a bit of madness here
    # first, selecting th with class="infobox-label which contains Symbolism in it's text
    # second, retrieve the td (table-data) using .matches[0].next - which gives next sibling to a tag
    # third, get a text of td and get rid of any [2] wikipedia stuff
    symbolism = parsed.select("th.infobox-label").text_contains("Symbolism").matches[0].next.text().split('[')[0].title()
    
    visibility = parsed.css_first("td.infobox-below").text()

    cursor = parsed.css_first("table.infobox.plainlist").next.next.child
    flavor_text =""
    while cursor.next is not None:
        if cursor.tag != "sup":
            flavor_text = f"{flavor_text}{cursor.text()}"
        cursor=cursor.next

    # lets chop up our flavor text a lil bit
    index_of_space = flavor_text.find(' ', 290, 320)
    flavor_text = flavor_text[:index_of_space]

    # get the start of a neighbours list
    # near_const = parsed.select("th.infobox-label").text_contains("Bordering").matches[0].next.css("not(sup)>a")
    near_const = parsed.select("th.infobox-label").text_contains("Bordering").matches[0].next

    # this line may be way too resourse-expensive
    near_const = [elem for elem in near_const.css("a[href]") if not elem.attributes["href"].startswith("#cite")]

    neighbours = "<ul>"
    for elem in near_const:
        if elem.tag != "sup":
            neighbours = f"{neighbours}<li>{elem.text()}</li>"

    image = parsed.css_first(".infobox-image")
    image = image.css_first("img").parent.attributes["href"]

    img_response = httpx.get(f"https://en.wikipedia.org{image}")
    parsed_img_response = HTMLParser(img_response.text)
    parsed_img_response = parsed_img_response.css_first("div.fullImageLink").css_first("img").attributes["src"]

    return {
        'shortdesc': short_desc,
        'symbolism': symbolism,
        'neighbours': neighbours,
        'visibility': visibility,
        'flavor_text' : flavor_text,
        'border_img' : parsed_img_response,
    }
