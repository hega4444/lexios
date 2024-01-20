# searchEngine.py

import feedparser
import yfinance
import openmeteo_requests
import requests_cache
import pandas as pd

from typing import List
from datetime import datetime
from retry_requests import retry
from newspaper import Article
from urllib.parse import urlparse, parse_qs, unquote

from lexios.core.common_tools import *


class SearchEngine():
    
    news_counter = 0
    news_dict = {}
    
    def __init__(self) -> None:
        pass

    @staticmethod
    def time_and_location() -> str:
        # KEYS: time date location weather prices
        # SUMM: Retrive current time / location

        # Prepare metadata, information that can enhance the quality of the assistant replies:
        week_day = curr_day_short()
        date_time, tzcode = get_adjusted_time()
        date_time = date_time.strftime("%Y-%m-%d %H:%M:%S")
        time_location = {
            "current_date_time": f"{week_day} {date_time}",
            "time_zone": f"{tzcode}",
        }
        return time_location
    
    @staticmethod
    def unwrap_url(redirected_url: str) -> str:
        parsed_url = urlparse(redirected_url)

        # For Bing's URL redirection
        if "bing.com" in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            original_url_encoded = query_params.get("url", [None])[0]
            if original_url_encoded:
                return unquote(original_url_encoded)

        # For Google's URL redirection
        elif "google.com" in parsed_url.netloc:
            query_params = parse_qs(parsed_url.query)
            original_url_encoded = query_params.get("q", [None])[0]
            if original_url_encoded:
                return unquote(original_url_encoded)

        # If no unwrapping pattern is recognized, return the original URL
        return redirected_url

    @classmethod
    def map_news_to_summary(cls, news_item):
        cls.news_counter += 1
        news_id = f"nid_{cls.news_counter:04}"  # Generates 'nid_XXXX' where XXXX is an incremented value
        title = news_item.get("title", "")
        summary = news_item.get("summary", "")
        url = next(
            (
                link["href"]
                for link in news_item.get("links", [])
                if link.get("rel") == "alternate"
            ),
            None,
        )

        # Internal update of NID to restore the url if needed.
        cls.news_dict.update(
            {news_id: {"title": title, "summary": summary, "url": SearchEngine.unwrap_url(url)}}
        )

        return {news_id: {"title": title, "summary": summary}}
    
    @staticmethod
    def read_rss(rss_url: str, keywords: List[str] = None) -> str:
        # KEYS: rss search real time information
        # SUMM: search for rss feeds in json format

        req_head = {"Accept-Language": "en-US,en;q=0.8"}

        # Parsing RSS feeds into JSON
        feed = feedparser.parse(rss_url, request_headers=req_head)
        entries = feed.entries

        # Optionally filter by keywords
        nid_dict = {}
        for entry in entries:
            if not keywords or any(
                kw.lower() in entry.title.lower() for kw in keywords
            ):
                nid_dict.update(SearchEngine.map_news_to_summary(entry))

        return json.dumps(nid_dict, indent=4)
    
    @staticmethod
    def bing_search(keywords: List[str]) -> str:
        # KEYS: how who when what which where what since know what's news check
        # SUMM: get real-time information from Bing search engine

        search = None
        # Treating the keywords in different ways depending the input format
        if isinstance(keywords, str):
            if "price" in keywords or "weather" in keywords:
                keywords += " on " + str(datetime.today())
            search = "%20".join(keywords.split())

        elif isinstance(keywords, list):
            if "price" in keywords or "weather" in keywords:
                keywords.append(str(datetime.today()))
            keywords = [k.replace(" ", "%20") for k in keywords]
            search = "%20".join(keywords)

        if search:
            try:
                rss_url = f"https://www.bing.com/news/search?q={search}&format=RSS"

                # Try to get results in english
                return SearchEngine.read_rss(rss_url=rss_url)
            except Exception as e:
                raise ValueError(f"Problems retrieving information from Bing. {e}")

    @classmethod
    def read_external_url_content(cls, url: str) -> str:
        # SUMM: extract html content from an url 

        article = Article(url)
        article.download()
        article.parse()

        article_data = {

            "title": article.title,
            "text": article.text,
            "authors": article.authors,
            "publish_date": article.publish_date.isoformat()
                if article.publish_date
                else None,
            "top_image": article.top_image,
            "keywords": article.keywords,
            "summary": article.summary,
        }

        return json.dumps(article_data, indent=4)
    
    @staticmethod
    def get_stock_price_by_symbol(symbol:str) -> str:
        # KEYS: stock price market share symbol company
        # SUMM: Retrieve latest known price for a specified symbol
        # symbol 'description': "symbol, i.e 'AAPL' ."
        
        # Define the stock symbol you want to fetch data for

        try:
            # Create a Ticker object for the stock symbol
            ticker = yfinance.Ticker(symbol)

            # Get the latest stock price
            latest_price = ticker.history(period="1d")["Close"].iloc[-1]

            # Round result to 4 decimals
            latest_price = round(latest_price, 4)
            
            return latest_price
        
        except Exception:
            return "Symbol not found."
    
    @staticmethod
    def get_weather_forecast(long: str, lat: str, number_days: int = 3) -> str:
    # KEYS: weather rain wind temperature forecast snow sunny clouds
    # SUMM: get a json dataframe with forecast to a number of days
    # lat 'description': latitude as float number, +N -S
    # long 'description': longitude as float number, +E -W

        try:
            try:
                latitude_ = float(lat)
                longitude_  = float(long)
            except Exception:
                return "{'status':'error', 'details':'latitude / longitude must be a float.' }"

            # Setup the Open-Meteo API client with cache and retry on error
            cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
            retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
            openmeteo = openmeteo_requests.Client(session = retry_session)

            # Make sure all required weather variables are listed here
            # The order of variables in hourly or daily is important to assign them correctly below
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": latitude_,
                "longitude": longitude_,
                "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation_probability", "precipitation"],
                "forecast_days": number_days
            }
            responses = openmeteo.weather_api(url, params=params)

            # Process first location. Add a for-loop for multiple locations or weather models
            response = responses[0]

            # Process hourly data. The order of variables needs to be the same as requested.
            hourly = response.Hourly()
            hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
            hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
            hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy()
            hourly_precipitation = hourly.Variables(3).ValuesAsNumpy()

            hourly_data = {"date": pd.date_range(
                start = pd.to_datetime(hourly.Time(), unit = "s"),
                end = pd.to_datetime(hourly.TimeEnd(), unit = "s"),
                freq = pd.Timedelta(seconds = hourly.Interval()),
                inclusive = "left"
            )}

            forecast = {}
            # Convert data into a dictionary:
            for index, hour in enumerate(hourly_data["date"]):
                # For each record:
                packed_data = {}
                packed_data['temp_c'] = round(float(hourly_temperature_2m[index]), 2)
                packed_data['relat_hum'] = float(hourly_relative_humidity_2m[index])
                packed_data['precip_prob'] = float(hourly_precipitation_probability[index])
                packed_data['precip'] = round(float(hourly_precipitation[index]), 3)
                
                # And append:
                h = str(hour)[2:-3]
                forecast[h] = packed_data

            # Create JSON response
            json_data = json.dumps(forecast)

            return json_data
        
        except Exception as e:
            print(e)
            return "No data found, check input parameters."
        

