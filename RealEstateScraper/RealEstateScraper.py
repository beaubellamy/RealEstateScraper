import os
import pandas as pd
import numpy as np
from pandas.io.json import json_normalize
import requests
import re, string, timeit
import time
from datetime import datetime, timedelta
import queue
from credentials import credentials

from datetime import datetime


def setup(file):
    
    # Todo: set up initialisation for new calling function
    # Some properties will be sold after a while, the price search may not work in this case....
    #    set a maximum before breaking out

    #client_id = credentials['client_id']
    #client_secret = credentials['client_secret']

    
    filename = os.path.join(os.path.join(os.path.dirname(os.path.realpath(__file__)),'..'),file)
    
    suburbs = ['Balgowlah', 'Manly Vale', 'Dee Why', 'Brookvale', 'Cremorne', 'Mosman']
    ##suburbs = ['NSW']

    # Limits of the post request enforced by Domain.com.au
    maxPages = 5

    # Build the first item for the serach queue
    locations = build_search_locations(suburbs)
    page=1
    pageSize=200
    searchForm = {
        'listingType': 'Sale',
        #'propertyTypes': None,
        #'propertyFeatures': None,
        #'listingAttributes': None,
        'minBedrooms': None,
        'maxBedrooms': None,
        'minBathrooms': None,
        'maxBathrooms': None,
        #'minCarspaces': None,
        #'maxCarspaces': None,
        'minPrice': None,
        'maxPrice': None,
        #'minLandArea': None,
        #'maxLandArea': None,
        #'advertiserIds': None,
        #'adIds': None,
        #'excludeAdIds': None,
        'locations': locations,
        #'locationTerms': None,
        'keywords': [],
        #'inspectionFrom': None,
        #'inspectionTo': None,
        #'auctionFrom': None,
        #'auctionTo': None,
        #'sort': None,
        'page': page,
        'pageSize': pageSize,
        #'geoWindow':None
        'sort': {'sortKey': 'Price',
                 'direction': 'Ascending'}
        }

    return filename, searchForm


def get_access_token(credentials={}):
    """
    Get the access token for the project.
    """
    client_id = credentials['client_id']
    client_secret = credentials['client_secret']

    if client_id == None or client_secret == None:
        return None

    # POST request for token
    response = requests.post('https://auth.domain.com.au/v1/connect/token', 
                             data = {'client_id':client_id,
                                     "client_secret":client_secret,
                                     "grant_type":"client_credentials",
                                     "scope":"api_listings_read api_listings_write",
                                     "Content-Type":"text/json"})
    token=response.json()
    expire = datetime.now() + timedelta(seconds=token['expires_in'])
    print (f'token expires at {expire}')

    access_token = {}
    access_token['access_token'] = token['access_token']
    access_token['expire_at'] = expire

    return access_token


def build_search_locations(suburbs=['Balgowlah']):
    """
    build the location parameters for the search parameters
    """

    postcode_file = os.path.join(os.path.join(os.path.dirname(os.path.realpath(__file__)),'..'),'postcodes.csv')
    postcodes = pd.read_csv(postcode_file)
    
    if 'NSW' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'NSW']
    if 'QLD' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'QLD']
    if 'SA' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'SA']
    if 'NT' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'NT']
    if 'ACT' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'ACT']
    if 'WA' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'WA']
    if 'TAS' in suburbs:
        postcodes = postcodes[postcodes['State'] == 'TAS']

    if set(suburbs).issubset(['All', 'NSW', 'QLD', 'SA', 'NT', 'ACT', 'WA', 'TAS']):
        suburbs = postcodes['Suburb']

    # buld the locations with additional parameters
    searchLocations = {}
    for suburb in suburbs:
        location_df = postcodes[postcodes['Suburb'] == suburb]

        if location_df.shape[0] > 0:
            location = {'state': location_df['State'].values[0], 
                        'suburb': location_df['Suburb'].values[0], 
                        'postcode': location_df['Postcode'].values[0],
                        'includeSurroundingSuburbs': True}
            searchLocations[suburb] = location
        else:
            print (f'{suburb} is not in the list.')

    return searchLocations


def get_access_token(credentials={}):
    """
    Get the access token for the project.
    """
    client_id = credentials['client_id']
    client_secret = credentials['client_secret']

    if client_id == None or client_secret == None:
        return None

    # POST request for token
    response = requests.post('https://auth.domain.com.au/v1/connect/token', 
                             data = {'client_id':client_id,
                                     "client_secret":client_secret,
                                     "grant_type":"client_credentials",
                                     "scope":"api_listings_read api_listings_write",
                                     "Content-Type":"text/json"})
    token=response.json()
    expire = datetime.now() + timedelta(seconds=token['expires_in'])
    print (f'token expires at {expire}')

    access_token = {}
    access_token['access_token'] = token['access_token']
    access_token['expire_at'] = expire

    return access_token


def search_builder(searchForm):
    """
    Build the search parameters list.
    """
    
    assert searchForm['listingType'] in ['Sale', 'Rent', 'Share', 'Sold', 'NewHomes'], \
        'listingType must be one of [Sale, Rent, Share, Sold, NewHomes]'
    
    # Build the search parameters with the locations
    locations = searchForm['locations']
    SearchParameters = []
    SearchQueue = queue.Queue()
    for suburb in locations.keys():
        searchForm['locations'] = [locations[suburb]]
        SearchParameters.append(searchForm.copy())
        SearchQueue.put(searchForm.copy())

    
    # The price range can be adjusted later, to reduce the number of listings returned (max 1000 per search)
    ''' 
    The choice to make the price adjustments later is because, when there is a list of locations, 
    the price ranges neccessary will depend on the number of locations included. If only one location 
    is included in the search, this limits the number of ranges that will be required to search through.
    '''

    return SearchParameters, SearchQueue


def remaining_calls(request):

    if 'X-RateLimit-Remaining' in request.headers.keys():
        remaining = request.headers['X-RateLimit-Remaining']
    elif 'X-Quota-PerDay-Remaining' in request.headers.keys():
        remaining = request.headers['X-Quota-PerDay-Remaining']
    else:
        remaining = -1

    return int(remaining)


def search_domain(token, search_parameters):
    """
    Return a list of all the listings that are relevant to the search parameters.
    """
    access_token = token['access_token']
    time.sleep(60)

    url = "https://api.domain.com.au/v1/listings/residential/_search"
    if datetime.now() > token['expire_at']:
        token = get_access_token(credentials)
        access_token = token['access_token']
    
    auth = {"Authorization":"Bearer "+access_token}

    while True:
        try:
            request = requests.post(url, json=search_parameters, headers=auth)
        except requests.exceptions.Timeout:
            # if timed out, try again later.
            time.sleep(60)
            request = requests.post(url, json=search_parameters, headers=auth)
        except requests.exceptions.TooManyRedirects as e:
            # The URL is wrong.
            print (f'Too many redirects: {e}')
            break
        except requests.exceptions.RequestException as e:
            # Request failed, try again later.
            now = datetime.now()
            print (f'{now}: Request Exception: {e}')
            print (f'Token expires: {token["expire_at"]}')
            time.sleep(60)
            request = requests.post(url, json=search_parameters, headers=auth)
        break

    # Test for specific status codes
    if request.status_code == 429:
        # Rate limit has been reached.
        retry_time = datetime.now() + timedelta(seconds=float(request.headers["Retry-After"]))
        quota = quota_limit(request)
        print (f'Limit of {quota} has been reached.')
        print (f'Will re-try at approx {retry_time}.')
        print (f'Access token expires at {token["expire_at"]}')

        time.sleep(float(request.headers['Retry-After'])*1.01)
        print (access_token)

        # Get a new token
        token = get_access_token(credentials)
        access_token = token['access_token']

        auth = {"Authorization":"Bearer "+access_token}
        request = requests.post(url, json=search_parameters, headers=auth)
        
        if request.status_code != 200:
            raise Exception(request.json()['errors'], request.json()['message'], 
                            'Raised after getting a new access token')

    if request.status_code != 200:
        # status code: 500
        raise Exception(request.json()['errors'], request.json()['message'])

    remaining = remaining_calls(request)

    return token, request.json(), remaining
    

def add_dates(listings, df):
    """
    Add the first and last seen dates to the dataframe
    """

    listing_df = json_normalize(listings)

    if df.shape[0] > 0:
        new_listings = listing_df['listing.id']
        mask = df['listing.id'].isin(new_listings)
        # Update the dates already in df
        df['last_seen'].loc[mask] = datetime.utcnow().date().strftime('%d/%m/%Y')
    
    listing_df['first_seen'] = datetime.utcnow().date().strftime('%d/%m/%Y')
    listing_df['last_seen'] = datetime.utcnow().date().strftime('%d/%m/%Y')
    
    listing_df = df.append(listing_df)
    
    # Sort the listings by date, so the last one is most recent
    listing_df = listing_df.sort_values(by=['last_seen'])
    listing_df = listing_df.drop_duplicates(subset='listing.id') # keep the last one
    
    return listing_df


def extract_price(lastPrice):
    """
    Extract the value of the price
    """
    
    price = 0
    priceDetails = lastPrice.replace('$','').replace(',','').replace('+','').replace('s','').split()
    for item in priceDetails:
        if item.isdigit():
            price = int(int(item)/100000)*100000
            break
        
    return price


def Domain(df, filename=None, searchForm={}):
    

    access_token = get_access_token(credentials)

    # Limits of the post request enforced by Domain.com.au
    maxPages = 5

    # Read the realestate file, if it exists
    #try:
    #    df = pd.read_csv(filename, sep=',')
    #    df.drop(['Unnamed: 0'], axis=1, inplace=True)
        
    #except FileNotFoundError:
    #    df = pd.DataFrame()

    # Build search paramters
    searchParameters, searchQueue = search_builder(searchForm)
    
    listings = []
    length = -1

    while searchQueue.qsize() > 0:
        print(f'Searching queue {searchQueue.qsize()}...')

        # Get the first item from the search queue
        search = searchQueue.get()
        access_token, search_results, remaining = search_domain(access_token, search)
        listings.extend(search_results)
     
        # Check if new listings can be added
        search['page'] += 1 
        access_token, new_listings, remaining = search_domain(access_token, search)

        while new_listings and search['page'] < maxPages:
            print (f'page: {search["page"]}')
            listings.extend(new_listings)

            # Add the next page of search results
            search['page'] += 1
            access_token, new_listings, remaining = search_domain(access_token, search)
 
        # Add the last page of search results
        listings.extend(new_listings)
    
        if ((len(new_listings) > 0) & (search['page'] >= maxPages)):
            # Update the search parameters when the maximum page count has been reached.
            # This uses the last price as the mimumum price in the next search criterea
            lastPrice = new_listings[-1]['listing']['priceDetails']['displayPrice']
            new_minPrice = extract_price(lastPrice)
            search['minPrice'] = new_minPrice
            search['page'] = 1
            searchQueue.put(search.copy())

        if remaining <= 5:
            # Update the dates and save to file if we are getting close to the call limit
            listing_df = add_dates(listings, df)
            listing_df.to_csv(filename)

    # Update the dates and save to file
    listing_df = add_dates(listings, df)
    listing_df = listing_df[listing_df['type'] != 'Project']
    listing_df.reset_index(drop=True, inplace=True)

    print (f'You have {remaining} api calls left.')
    listing_df.to_csv(filename)

    return access_token, listing_df, remaining


# Remove the dates from the price field
def remove_dates(df, pattern):
    df['date_in_price'] = df['listing.priceDetails.displayPrice'].str.findall(pattern, re.IGNORECASE)

    # Replace the date in the display price
    for idx, row in df.iterrows():
        if row['date_in_price']:
            removed_date = row['listing.priceDetails.displayPrice'].replace(row['date_in_price'][0],'')
            df.loc[idx, 'listing.priceDetails.displayPrice'] = removed_date

    df.drop(['date_in_price'], axis=1, inplace=True)

    return df


def remove_times(df, pattern):

    df['time_in_price'] = df['listing.priceDetails.displayPrice'].str.findall(pattern)

    if sum(df['time_in_price'].str[0].isnull()) == 0:
        df.drop(['time_in_price'], axis=1, inplace=True)
        return df

    # Replace the time in the display price
    mask = ~df['time_in_price'].str[0].isnull()
    if sum(mask) > 0:
        if 'time_in_price' not in list(df.columns):
            print ('stop')

        df.loc[mask, 'listing.priceDetails.displayPrice'] = \
            df[mask]['listing.priceDetails.displayPrice'].str.replace(df['time_in_price'][df[mask].index[0]][-1],'')

    df.drop(['time_in_price'], axis=1, inplace=True)

    return df


def remove_phone_numbers(df):

    # Remove phone numbers
    pattern = '\d{4} \d{3} \d{3}'
    df['phone_number'] = df['listing.priceDetails.displayPrice'].str.findall(pattern)

    # Replace the date in the display price
    for idx, row in df.iterrows():
        if row['phone_number']:
            phone_number = row['listing.priceDetails.displayPrice'].replace(row['phone_number'][0],'')
            df.loc[idx, 'listing.priceDetails.displayPrice'] = phone_number

    df.drop('phone_number', axis=1, inplace=True)

    return df


def extend_numbers(df, pattern, delimiter=' '):

    df['alt'] = df['listing.priceDetails.displayPrice'].str.findall(pattern, flags=re.IGNORECASE)#.str[0].str.lower()   

    if sum(df['alt'].str[0].isnull()) == df.shape[0]:
        df.drop(['alt'], axis=1, inplace=True)
        return df
    
    df['float_value'] = df['alt'].str[0].str.split(delimiter).str[0].astype(float)*1e6
    #df['float_value'] = df['alt'].str.split(delimiter).str[0].astype(float)*1e6
    df['replace_value'] = df['float_value'].fillna(0).astype(int)
    df.loc[df['alt'].isnull(), 'alt'] = ''

    for idx, row in df.iterrows():

        if row['alt']:
            extend_number = row['listing.priceDetails.displayPrice'].lower().replace(row['alt'][0],str(row[f'replace_value']))
            df.loc[idx, 'listing.priceDetails.displayPrice'] = extend_number

    df.drop(['alt', 'float_value', 'replace_value'], axis=1, inplace=True)
    
    return df

def extend_numbers2(df, pattern, delimiter=' '):

    df['alt'] = df['listing.priceDetails.displayPrice'].str.findall(pattern, flags=re.IGNORECASE)#.str[0].str.lower()   

    if sum(df['alt'].str[0].isnull()) == df.shape[0]:
        df.drop(['alt'], axis=1, inplace=True)
        return df

    if delimiter == 'k':
        multiplier = 1e3
    elif delimiter == 'm':
        multiplier = 1e6
    else:
        multiplier = 1
        # 214, 221, 282, 422
    #df['float_value'] = df['alt'].str[0].str.split(delimiter).str[0].astype(float)*1e6
    df['float_value'] = df['alt'].str[0].str.split(delimiter).str[0].astype(float)*multiplier
    df['replace_value'] = df['float_value'].fillna(0).astype(int)
    df.loc[df['alt'].isnull(), 'alt'] = ''

    for idx, row in df.iterrows():

        if row['alt']:
            extend_number = row['listing.priceDetails.displayPrice'].replace(row['alt'][0],str(row['replace_value']))
            df.loc[idx, 'listing.priceDetails.displayPrice'] = extend_number

    df.drop(['alt', 'float_value', 'replace_value'], axis=1, inplace=True)
    
    return df


def listing_prices(df):

    #df = pd.read_csv(filename, sep=',')
    #df.drop(['Unnamed: 0'], axis=1, inplace=True)

    # Todo: Make sure all listings have a real price
    # extract prices where available.
    # identify listings with no price and then price range function
    df['listing.priceDetails.displayPrice'] = df['listing.priceDetails.displayPrice'].fillna('none')
    null_price = df['listing.priceDetails.price'].isnull()

    # If the display price feature has a number, this is likely to be the price or dates
    # This is not expected to happen too often.
    display_is_number = df['listing.priceDetails.displayPrice'].str.isdigit()
    df.loc[(null_price & display_is_number), 'listing.priceDetails.price'] = \
        df[null_price & display_is_number]['listing.priceDetails.displayPrice']

    df['listing.priceDetails.displayPrice'] = df['listing.priceDetails.displayPrice'].str.lower()

    #361???? --> 15000001510000, 377,627
    # Remove the agent phone numbers
    df = remove_phone_numbers(df)

    # Replace the time and date parts of the display price before finding the price, so the numbers are only price
    # Remove the numbers related to time
    time_pattern = '\d{1,2}\.\d{1,2}[ap]'
    df = remove_times(df, time_pattern)

    time_pattern = '\d:\d{2}' # 2:30-3:00pm
    df = remove_times(df, time_pattern)

    # Remove the numbers related to dates (May 30)
    date_pattern = r'(?=Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}'
    df = remove_dates(df, date_pattern)

    # (30 May)
    date_pattern = r'\d{1,2} (?=Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    df = remove_dates(df, date_pattern)

    # 1st, 2nd, 30th
    date_pattern = '[0-9]{1,2}[snrt]'
    df = remove_dates(df, date_pattern)

    # Remove other phrases with numbers in them
    # eg: 'sold in 7 days' or 'land 999m2'
    pattern = '\d{1,2} (?=day)'
    df = remove_dates(df, pattern)

    pattern = '\d{2,4}\w2'
    df = remove_dates(df, pattern)

    pattern = r'(\d{1,3}k)'
    df = extend_numbers2(df, pattern, delimiter='k')
    df = extend_numbers2(df, pattern, delimiter='k') # accounts for '$900k - $950k

    pattern = r'(\d{1,3} k)'
    df = extend_numbers2(df, pattern, delimiter='k')

    pattern = r'(\d{1}.{1,3} mill)'
    df = extend_numbers(df, pattern)

    pattern = r'\d{1,3} mill'
    df = extend_numbers(df, pattern)

    pattern = r'\d.\d{1,3}m$'
    df = extend_numbers(df, pattern, delimiter='m')

    df = extend_numbers(df, pattern, delimiter='m') # accounts for $1.1m - $1.2m

    # Create clean price features
    df['listing.priceDetails.displayPrice'] = df['listing.priceDetails.displayPrice'].str.replace(',','')
    df['displayPrice'] = df['listing.priceDetails.displayPrice'].str.findall('\d{1,7}')

    df['fromPrice'] = df['listing.priceDetails.priceFrom']
    df['toPrice'] = df['listing.priceDetails.priceTo']

    # Seperate clean prices
    df.loc[null_price, 'fromPrice'] = df[null_price]['displayPrice'].str[0]#.split('-').str[0]
    df.loc[null_price, 'toPrice'] = df[null_price]['displayPrice'].str[1]#.split('-').str[1]

    null_toPrice = df['toPrice'].isnull()
    df.loc[null_toPrice, 'toPrice'] = df[null_toPrice]['fromPrice']

    #empty_price = df['toPrice'] == ''
    #df.loc[empty_price, 'toPrice'] = df[empty_price]['fromPrice']

    #empty_price = df['fromPrice'] == ''
    #df.loc[empty_price, 'fromPrice'] = df[empty_price]['toPrice']

    df['toPrice'] = pd.to_numeric(df['toPrice'])
    df['fromPrice'] = pd.to_numeric(df['fromPrice'])

    df.loc[((df['toPrice'] != 0) & (df['toPrice'] <= 1200)), 'toPrice'] = np.nan
    df.loc[((df['fromPrice'] != 0) & (df['fromPrice'] <= 1200)), 'fromPrice'] = np.nan

    #df.to_csv(filename)

    return df


def quota_limit(request):

    if 'x-ratelimit-vcallrate' in request.headers.keys():
        quota = request.headers['x-ratelimit-vcallrate']
    elif 'X-Quota-PerDay-Limit' in request.headers.keys():
        quota = request.headers['X-Quota-PerDay-Limit']
    else:
        quota = -1

    return quota


def validate_get_request(url, token, credentials):

    auth = {"Authorization":"Bearer "+token['access_token']}
    request = requests.get(url, headers=auth)
    
    # check for status.
    if request.status_code == 429:
        # Rate limit has been reached.
        retry_time = datetime.now() + timedelta(seconds=float(request.headers["Retry-After"]))
        quota = quota_limit(request)
        print (f'Limit of {quota} has been reached.')
        print (f'Will re-try at approx {retry_time}.')
        #print (f'Access token expires at {token["expire_at"]}')

        time.sleep(float(request.headers['Retry-After']))
        time.sleep(60)

        #print (access_token)

        # Get a new token
        token = get_access_token(credentials)
        access_token = token['access_token']

        auth = {"Authorization":"Bearer "+access_token}
        request = requests.get(url,headers=auth)
        
        if request.status_code != 200:
            raise Exception(request.json()['errors'], request.json()['message'], 
                            'Raised after getting a new access token')
    
    elif request.status_code == 404:
        print(f'{url} not found')
        return 'Not Found', token

    if request.status_code != 200:
        raise Exception(request.json()['errors'], request.json()['message'], 
                            'Raised after getting a new access token')

    return request, token


def build_post_fields(property_fields):
        
    post_fields ={
        "listingType":"Sale",
        "maxPrice":property_fields['price'],
        "pageSize":100,
        "propertyTypes":property_fields['propertyTypes'],
        "minBedrooms":property_fields['bedrooms'],
        "maxBedrooms":property_fields['bedrooms'],
        "minBathrooms":property_fields['bathrooms'],
        "maxBathrooms":property_fields['bathrooms'],
        "locations":[
        {
            "state":"",
            "region":"",
            "area":"",
            "suburb":property_fields['suburb'],
            "postCode":property_fields['postcode'],
            "includeSurroundingSuburbs":False
        }
        ]
    }

    return post_fields


def validate_post_request(url,  token , post_payload, credentials):

    auth = {"Authorization":"Bearer "+token['access_token']}
    
    try:
        request = requests.post(url, headers=auth, json=post_payload) #------
    except requests.exceptions.ConnectionError:
        time.sleep(3600)
        request = requests.post(url, headers=auth, json=post_payload)

    #token=request.json()
    while request.status_code == 504:
        time.sleep(3600)
        request = requests.post(url, headers=auth, json=post_payload)

    if request.status_code == 502:
        print (f'Connection lost: waiting 30 sec for retry [quota: {quota_limit(request)}]')
        time.sleep(30)
        #token = get_access_token(credentials)
        #access_token = token['access_token']

        #auth = {"Authorization":"Bearer "+access_token}
        # retry the request, we may need to get a new token 
        request = requests.post(url, json=post_payload, headers=auth)

        if request.status_code != 200:
            raise Exception(request.json()['errors'], request.json()['message'], 
                            'Raised after getting a new access token')

    # check for status.
    if request.status_code == 429:
        # Rate limit has been reached.quota_limit(request)
        retry_time = datetime.now() + timedelta(seconds=float(request.headers["Retry-After"]))
        quota = quota_limit(request)
        print (f'Limit of {quota} has been reached.')
        print (f'Will re-try at approx {retry_time}.')
        #print (f'Access token expires at {token["expire_at"]}')

        time.sleep(float(request.headers['Retry-After']))
        time.sleep(60)
        # *** Follow request through 'check_for_listing' [Response 401] 
        # Get a new token
        token = get_access_token(credentials)
        access_token = token['access_token']

        auth = {"Authorization":"Bearer "+access_token}
        request = requests.post(url, json=post_payload, headers=auth)
        print (token['access_token'])

        if request.status_code != 200:
            raise Exception(request.json()['errors'], request.json()['message'], 
                            'Raised after getting a new access token')

    if request.status_code != 200:
        print (f'{request.json()["errors"]}: {request.json()["message"]} Raised after getting a new access token')
        return "Failed", token

    return request, token


def check_for_listing(request, property_id, price, increment, increase_price=True):

    continue_searching = True

    if increase_price == True:
        prefix = 'Lower'
        search_prefix = 'increasing'
    else:
        prefix = 'Upper'
        search_prefix = 'decreasing'

    listing_request=request.json()
    listings = []
    
    for listing in listing_request:
        if 'listing' in listing.keys():
            listings.append(listing['listing']['id'])
        elif 'listings' in listing.keys():
            [listings.append(l['id']) for l in listing['listings']]

    
    if increase_price == True:
        if int(property_id) in listings:
            print(f"{prefix} bound found: ", price)
            #min_price=min_price-increment
            continue_searching=False
        else:
            price=price+increment
    else:
        if int(property_id) not in listings:
            price+=increment
            print(f"{prefix} bound found: ", price)
            #min_price=min_price-increment
            continue_searching=False
        else:
            price=price-increment
        
    if continue_searching:
        print(f"Not found. {search_prefix} price to {price}")
    
    time.sleep(0.1)  # sleep a bit so you don't make too many API calls too quickly   

    return continue_searching, price


def find_price_range(token, property_id, lowerBoundPrice, UpperBoundPrice, increment):
    """
    Find the price range of a property listing
    access_token: Must be a valid access token for the project.
    property_id: The unique property id at the end of the url 
    """
   
    

    # Function prints the property details and whether each price guess has the property listed.

    # Get the property details
    url = "https://api.domain.com.au/v1/listings/"+str(int(property_id))
    auth = {"Authorization":"Bearer "+token['access_token']}
    request, token = validate_get_request(url, token, credentials)
    #request = requests.get(url,headers=auth)
    
    if request == 'Not Found':
        print ('request wasnt found')
        return None, 0, 0, token, -9
   
    details=request.json()

    if details['status'] == 'sold':
        if 'soldDate' in details['saleDetails']['soldDetails'].keys():
            date = details['saleDetails']['soldDetails']['soldDate']
        else:
            date = None

        price = 0
        if 'soldPrice' in details['saleDetails']['soldDetails'].keys():
            price = details['saleDetails']['soldDetails']['soldPrice']
        
        remaining = remaining_calls(request)
        print ('listing was sold')

        return date, price, price, token, int(remaining)

    # Get the property details
    address=details['addressParts']
    postcode=address['postcode']
    suburb=address['suburb']
    bathrooms=details['bathrooms']
    bedrooms=details['bedrooms']
    property_type=details['propertyTypes']
    print(f'Property: {property_type} \nAddress: {suburb}, {postcode} \n'
          f'Bedrooms:{str(bedrooms)}, \nBathrooms:{str(bathrooms)}')

    # The below puts all relevant property types into a single string. eg. a property listing 
    # can be a 'house' and a 'townhouse'
    #property_type_str=""
    #for p in details['propertyTypes']:
    #    property_type_str=property_type_str+(p)

    min_price=lowerBoundPrice
    continue_searching=True
    details['postcode'] = address['postcode']
    details['suburb'] = address['suburb']

    # Start your loop
    while continue_searching:
        
        details['price'] = min_price

        url = "https://api.domain.com.au/v1/listings/residential/_search" # Set destination URL here
        post_fields = build_post_fields(details)
        
        #request = requests.post(url,headers=auth,json=post_fields)
        request, token = validate_post_request(url, token, post_fields, credentials)
        if request == 'Failed':
            print ('request failed')
            return None, min_price, min_price, token, -1

        remaining = remaining_calls(request)

        
        continue_searching, min_price = check_for_listing(request, property_id, min_price, increment, True)
               
        #if continue_searching and min_price == UpperBoundPrice:
        #    UpperBoundPrice *= 2
        #    print ('stop')

        if min_price == 5000000:
            # return early if the proces are too high
            remaining = remaining_calls(request)
            return None, min_price, min_price, token, remaining

    continue_searching=True
    UpperBoundPrice = int(min_price*1.2)
    max_price = UpperBoundPrice
    #if UpperBoundPrice>0:
    #    max_price=UpperBoundPrice
    #else:  
    #    max_price=min_price+400000  


    while continue_searching:
    
        details['price'] = max_price

        url = "https://api.domain.com.au/v1/listings/residential/_search" # Set destination URL here
        post_fields = build_post_fields(details)
                
        request, token = validate_post_request(url,  token, post_fields, credentials)
        if request == 'Failed':
            print ('request failed')
            return None, min_price, min_price, token, remaining

        remaining = remaining_calls(request)
        
        continue_searching, max_price = check_for_listing(request, property_id, max_price, increment, False)

        # If the maximum price is greater than the upper bound, the real price was not
        # found. Increase the upper bound and continue searching
        if not continue_searching and max_price >= UpperBoundPrice:
            UpperBoundPrice *= 2
            #max_price = UpperBoundPrice
            continue_searching = True

        #if max_price <= lowerBoundPrice:
        #    lower = 1
        #    break
    
    # Print the results
    print(address['displayAddress'])
    print(details['headline'])
    print("Property Type:",details['propertyTypes'])
    print("Details: ",int(bedrooms),"bedroom,",int(bathrooms),"bathroom")
    print("Display price:",details['priceDetails']['displayPrice'])      
    if min_price==max_price:
        print(f'Price guide: ${min_price}')
    else:
        print(f'Price range: ${min_price} - ${max_price}')
    print("URL:",details['seoUrl'])

    remaining = remaining_calls(request)

    return None, min_price, max_price, token, remaining


def DomainPriceFinder(df, access_token, remianing, filename, break_flag):

    #file = 'local_listings.csv'
    #filename = os.path.join(os.path.join(os.path.dirname(os.path.realpath(__file__)),'..\\..\\DomainRealestate\\'),file)
    #filename  = 'C:\\Users\\Beau\\Documents\\DataScience\\DomainRealestate\\local_listings.csv'
    
    #access_token, df = Domain(filename=filename, searchForm=searchForm)
    #access_token = get_access_token(credentials) # only required when not calling Domain

    ## extract the prices in to something usefull
    df = listing_prices(df) ### -- alter for dataframe
    #df['Sold Date'] = None
    
    # find prices by calling the search api
    # Find prices where there is none.
    id_list = df[(df['fromPrice'].isnull()) | (df['toPrice'].isnull())]
    for idx, row in id_list.iterrows():
     
        date, min_price, max_price, access_token, remaining = find_price_range(access_token, row['listing.id'], 500000, 2000000, 25000)

        df.loc[idx, 'listing.priceDetails.price'] = 'price search'
        df.loc[idx, 'listing.priceDetails.priceFrom'] = min_price
        df.loc[idx, 'fromPrice'] = min_price
        df.loc[idx, 'listing.priceDetails.priceTo'] = max_price
        df.loc[idx, 'toPrice'] = max_price

        if date is not None:
            df.loc[idx, 'Sold Date'] = date

        # Update the file before we run out of api calls.
        df.to_csv(filename)

        print (f'remaining calls: {remaining}')

        # If its the right day to search for more listings, break out early
        #if int(datetime.today().strftime('%j')) % 3 == 0 and break_flag:
        #    break

    missing_prices = df[(df['fromPrice'].isnull()) | (df['fromPrice'].isnull())].shape[0]
    #print (f'There are {missing_prices} listings that are missing price information.')

    return access_token, remaining


if __name__ == '__main__':
    
    file = 'local_listings.csv'
    filename, searchForm = setup(file)
    breakouts = 0

    today = int(datetime.today().strftime('%j'))
    remaining = 1


    # Read the realestate file, if it exists
    try:
        df = pd.read_csv(filename, sep=',')
        df.drop(['Unnamed: 0'], axis=1, inplace=True)
        
    except FileNotFoundError:
        df = pd.DataFrame()

    access_token = get_access_token(credentials)

    while True:
    #for i in range(366):
        #i = i + 1
        today = int(datetime.today().strftime('%j'))
        #break_flag = True

        if today % 3 == 0 and breakouts <= 1:
            filename, searchForm = setup(file)
            access_token, df, remaining = Domain(df, filename=filename, searchForm=searchForm)
            print (f'listings {remaining}; dataframe size {df.shape}')
            #previous = today
            #break_flag = False

        # Check the first few listing prices are being stored. price = 0
        #access_token, remaining = DomainPriceFinder(df, access_token, remaining, filename, break_flag)
        #print (f'{i} price: {remaining}')

        ## extract the prices in to something usefull
        df = listing_prices(df) ### -- alter for dataframe
        #df['Sold Date'] = None
    
        # find prices by calling the search api
        # Find prices where there is none.
        id_list = df[(df['fromPrice'].isnull()) | (df['toPrice'].isnull())]
        for idx, row in id_list.iterrows():
            today = int(datetime.today().strftime('%j'))
            date, min_price, max_price, access_token, remaining = find_price_range(access_token, row['listing.id'], 500000, 2000000, 25000)

            df.loc[idx, 'listing.priceDetails.price'] = 'price search'
            df.loc[idx, 'listing.priceDetails.priceFrom'] = min_price
            df.loc[idx, 'fromPrice'] = min_price
            df.loc[idx, 'listing.priceDetails.priceTo'] = max_price
            df.loc[idx, 'toPrice'] = max_price

            if date is not None:
                df.loc[idx, 'Sold Date'] = date

            # Update the file before we run out of api calls.
            df.to_csv(filename)

            print (f'shape: {df.shape} remaining calls: {remaining}') # Add the df shape to keep track of changes

            # If its the right day to search for more listings, break out early 
            if today % 3 == 0:
                breakouts += 1
                break
            else:
                breakouts = 0

            missing_prices = df[(df['fromPrice'].isnull()) | (df['fromPrice'].isnull())].shape[0]

