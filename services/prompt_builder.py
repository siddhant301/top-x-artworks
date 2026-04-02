import httpx
import json
from datetime import datetime

# The chart_data_formatter module remains at the top level
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chart_data_formatter import format_chart_data_for_llm

GRAPHQL_URL = "https://gql.test.mutualart.com/api/graphql"

# In a production app, AUTH_TOKEN should ideally be in .env, but keeping as requested
AUTH_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InNpZGRoYW50QG11dHVhbGFydC5jb20iLCJwbGF0Zm9ybSI6ImNvbnNvbGUiLCJleHAiOjI0MDYwNjcyMDAsImlzcyI6Imh0dHBzOi8vbG9jYWxob3N0OjcyMzAifQ.i6yrRM5X8LqCki9uXNHriDaC_xgCxk7ANf9NB-tmtwQ"

def get_client() -> httpx.AsyncClient:
    """Create a configured httpx AsyncClient to reuse connections."""
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    return httpx.AsyncClient(verify=False, headers=headers, timeout=30.0)

async def fetch_top_5_expensive(client: httpx.AsyncClient, artist_id):
    """
    Query 1: Get the top 5 most expensive paintings for the artist.
    """
    query = """
    query ArtistTopSoldLots($_artists: [String]){
      artworks(filter:[{artists:$_artists},{status:Sold},{isLot:true}],order:[PRICE_DESC],size:5){
        data{
          id
        }
      }
    }
    """
    variables = {
        "_artists": [artist_id]
    }
    
    response = await client.post(GRAPHQL_URL, json={'query': query, 'variables': variables})
    response.raise_for_status()
    data = response.json()
    
    if 'errors' in data:
        raise Exception(f"GraphQL Errors: {data['errors']}")
        
    artworks = data.get('data', {}).get('artworks', {}).get('data', [])
    return [aw['id'] for aw in artworks]

async def fetch_artwork_details(client: httpx.AsyncClient, artwork_ids):
    """
    Query 2: Fetch detailed information for each of the top 5 painting IDs.
    """
    query = """
    query LotsPartial(
        $_pageSize: Int, 
        $_skip: Int, 
        $_order: [ArtworkOrder], 
        $_id: [String] 
    ){
      data: artworks(
            size: $_pageSize, 
            skip: $_skip, 
            filter: [          
              {id:$_id}
            ],
            order: $_order
      ){  
        count
        data {
          id
          url
          name
          dateText
          fromYear
          mediumText
          isSigned
          editionNumber
          dimensionsDescr
          showPrice
          artworkDescription {
            description
            caption
          }
          provenance
          exhibitionHistory
          lot {
            id
            realizedPrice
            realUsd
            currency
            name
            lotNo
            date
            event {
              url
              mainOrganization{
                    id
                    name
                    url
                }
              organizations{
                id
                name
              }
              location{
                city{
                  name
                }
              }
            }
          }
          artworkArtist {
            artist {
              id
              name
              displayName
            }
          }
        }
      }
    }
    """
    variables = {
        "_id": artwork_ids,
        "_pageSize": len(artwork_ids),
        "_skip": 0
    }
    
    response = await client.post(GRAPHQL_URL, json={'query': query, 'variables': variables})
    response.raise_for_status()
    data = response.json()
    
    if 'errors' in data:
        raise Exception(f"GraphQL Errors: {data['errors']}")
        
    return data.get('data', {}).get('data', {}).get('data', [])

def build_prompt_context(artworks):
    """
    Process the GraphQL response into the specific JSON format for the prompt.
    """
    if not artworks:
        return "", "Unknown Artist"
        
    # Extract the artist's name
    artist_name = "Unknown Artist"
    artists_list = artworks[0].get('artworkArtist', [])
    if artists_list:
        artist_data = artists_list[0].get('artist', {})
        artist_name = artist_data.get('name') or artist_data.get('displayName', 'Unknown Artist')
                
    top_works = []
    
    for aw in artworks:
        lot = aw.get('lot') or {}
        event = lot.get('event') or {}
        
        # Format Realized Price
        realized_price = lot.get('realUsd') or lot.get('realizedPrice')
        currency = "USD" if lot.get('realUsd') else lot.get('currency', 'USD')
        
        if realized_price is not None:
            try:
                price_str = f"{float(realized_price):,.0f} {currency}"
            except (ValueError, TypeError):
                price_str = f"{realized_price} {currency}"
        else:
            price_str = "Price not disclosed"
            
        # Format Sale Date
        sale_date_raw = lot.get('date')
        sale_date_formatted = sale_date_raw
        if sale_date_raw:
            try:
                dt = datetime.fromisoformat(sale_date_raw.replace('Z', '+00:00'))
                sale_date_formatted = dt.strftime("%d %B, %Y")
            except Exception:
                pass
                
        # Format Auction Venue
        main_org = event.get('mainOrganization') or {}
        venue_name = main_org.get('name', '')
        if not venue_name:
            orgs = event.get('organizations') or []
            if orgs:
                venue_name = orgs[0].get('name', '')
                
        city = (event.get('location') or {}).get('city', {}).get('name', '')
        auction_venue = f"{venue_name} {city}".strip() if venue_name else "Unknown Venue"
            
        # Format URL
        url_raw = aw.get('url', '')
        view_at = "https://www.mutualart.com" + url_raw if url_raw.startswith('/') else url_raw
            
        work_data = {
            "title": aw.get('name', 'Untitled'),
            "date": aw.get('dateText') or str(aw.get('fromYear', 'N/A')),
            "medium": aw.get('mediumText', 'Unknown medium'),
            "dimensions": aw.get('dimensionsDescr', 'Dimensions unavailable'),
            "realizedPrice": price_str,
            "saleDate": sale_date_formatted or 'Unknown date',
            "auctionVenue": auction_venue,
            "viewAt": view_at,
            "provenance": aw.get('provenance', ''),
            "exhibitionHistory": aw.get('exhibitionHistory', '')
        }
        top_works.append(work_data)
        
    context_json = {
        "artist": artist_name,
        "top_works": top_works
    }
    
    return json.dumps(context_json, indent=2, ensure_ascii=False), artist_name

async def fetch_chart_data(client: httpx.AsyncClient, artist_id):
    """
    Query 3: Fetch chart data for artist turnover using the ChangeInTotalSales query
    """
    query = """
    query ChangeInTotalSales($estStart: Float, $estEnd: Float, $soldStart: Float, $soldEnd: Float, $artworkYearStart: Float, $artworkYearEnd: Float, $dateStart: DateTime, $dateEnd: DateTime, $similarTo: [String], $status: [LotStatusType], $isUpcoming: Boolean, $isUpcomingAnd: Boolean, $price: NumberRange, $priceEUR: NumberRange, $priceGBP: NumberRange, $phrase: String, $artists: [String], $artistType: [ArtworkArtist], $nationalities: [String], $auctionVenues: [String], $locations: [String], $tags: [String], $year: NumberRange, $height: NumberRange, $width: NumberRange, $lotIds: NumberRange, $saleTitle: String, $saleNumber: String, $estimate: NumberRange, $isLot: Boolean, $hasImage: Boolean, $mediumText: String, $auctionId: String, $onlyFollowed: Boolean, $artistCount: Float, $hasProvenance: Boolean, $hasCondition: Boolean, $hasExhbHistory: Boolean, $hasLiterature: Boolean, $isSigned: Boolean, $artworkOrientation: ArtworkOrientation) {
      artworks(filter: [{estimatePrice: {start: $estStart, end: $estEnd}}, {soldPrice: {start: $soldStart, end: $soldEnd}}, {fromYear: {start: $artworkYearStart, end: $artworkYearEnd}}, {saleDate: {start: $dateStart, end: $dateEnd}}, {similarTo: $similarTo}, {mediumText: $mediumText}, {estimatePrice: $estimate}, {hasImage: $hasImage}, {isLot: $isLot}, {status: $status, isUpcoming: $isUpcoming}, {isUpcoming: $isUpcomingAnd}, {price: $price}, {priceEUR: $priceEUR}, {priceGBP: $priceGBP}, {artists: $artists}, {artistType: $artistType}, {nationalityIds: $nationalities}, {organizationIds: $auctionVenues}, {locationIds: $locations}, {text: $phrase}, {broadMediaIds: $tags}, {fromYear: $year}, {dimensionsHeightCm: $height}, {dimensionsWidthCm: $width}, {lotNum: $lotIds}, {saleNumber: $saleNumber}, {eventTitle: $saleTitle}, {auctionId: $auctionId}, {onlyFollowed: $onlyFollowed}, {artistCount: {start: $artistCount}}, {hasProvenance: $hasProvenance, hasCondition: $hasCondition, hasExhbHistory: $hasExhbHistory, hasLiterature: $hasLiterature}, {isSigned: $isSigned}, {artworkOrientation: $artworkOrientation}]) {
        count
        aggregation {
          saleDate(period: YEAR, periodCount: 1, filter: {status: Sold}, returnRange: {start: $dateStart, end: $dateEnd}) {
            key
            price(currency: USD) {
              LotSold: count
              Realized_Auction_Prices: sum
              Median_Price: median
            }
          }
          offerd: saleDate(period: YEAR, periodCount: 1, returnRange: {start: $dateStart, end: $dateEnd}) {
            key
            saleDate {
              offered: count
            }
          }
        }
      }
    }
    """
    
    variables = {
      "similarTo": None,
      "mediumText": "",
      "hasImage": None,
      "isLot": True,
      "artistCount": 0,
      "status": [],
      "isUpcoming": None,
      "isUpcomingAnd": None,
      "auctionId": "",
      "estimate": {
        "start": None,
        "end": None
      },
      "artists": [artist_id],
      "artistType": [],
      "nationalities": [],
      "auctionVenues": [],
      "locations": [],
      "phrase": "",
      "tags": None,
      "year": {
        "start": None,
        "end": None
      },
      "height": None,
      "width": None,
      "saleDate": {
        "start": None,
        "end": None
      },
      "lotIds": {
        "start": None,
        "end": None
      },
      "saleTitle": "",
      "saleNumber": "",
      "onlyFollowed": False,
      "hasProvenance": None,
      "hasCondition": None,
      "hasExhbHistory": None,
      "hasLiterature": None,
      "dateStart": "2002-01-01 00:00",
      "dateEnd": "2026-12-31 00:00",
      "currency": "",
      "isSigned": None,
      "artworkOrientation": None,
      "price": {
        "start": None,
        "end": None
      }
    }
    
    response = await client.post(GRAPHQL_URL, json={'query': query, 'variables': variables})
    response.raise_for_status()
    data = response.json()
    
    if 'errors' in data:
        raise Exception(f"GraphQL Errors: {data['errors']}")
        
    return data

async def build_article_prompt(artist_id):
    """
    Main entry point for generating the prompt text using httpx.AsyncClient for performance.
    """
    # Use context manager to automatically close the session once we're done
    async with get_client() as client:
        # 1. Fetch Top 5 IDs
        top_ids = await fetch_top_5_expensive(client, artist_id)
        if not top_ids:
            return None
            
        # 2. Fetch Detailed Artwork Fields
        details = await fetch_artwork_details(client, top_ids)
        if not details:
            return None
            
        # 3. Build the JSON string and extract artist name
        context_str, artist_name = build_prompt_context(details)
        
        # 4. Fetch Chart Data
        chart_data_raw = await fetch_chart_data(client, artist_id)
        chart_data_str = format_chart_data_for_llm(chart_data_raw)
        
        # 5. Construct Final Text Prompt
        final_prompt = f"""Prompt: Analytical Overview of {artist_name}'s Auction Milestones
[Data Input Block: GraphQL Source]
Instructions for AI: Use the structured data below to populate the article.

Hyperlinks: Embed the viewAt URL into the artwork title in each Lot Header.

Provenance: Extract only the single most prestigious owner/gallery from the provenance string.

Exhibition: Extract only the primary museum/gallery name and year from exhibitionHistory.

Market Context: Reference the provided "Artist Auction Market Data" below to identify specific years where total sales crossed major thresholds (e.g., $120m, $240m, or $360m).

Active Data:

{context_str}

Chart Data:

{chart_data_str}

[Editorial Instructions]
Objective: Write an 800–1000 word article for MutualArt analyzing the artist’s 5 most expensive works.

Header & Lead (The "Munch" Standard):

Main Title: {artist_name}’s 5 Most Expensive Works: [Subtitle]

Deck (Italicized): A 40–60 word qualitative summary of the artist’s thematic essence and scarcity. Strictly no numbers or years.

Publication: MutualArt | [Current Date]

The Lead Paragraph: Write a 100–150 word "Titan of Art" introduction. Focus on the artist as a progenitor of their movement. Contrast the rarity of major oils with traded prints. Discuss the demand as a translation of human experience/anxiety. Strictly no numbers, prices, or data points.

Lot Analysis Rules:

Lot Header Format: [Number]. [Hyperlinked Title], [Year] – [Price] USD. [Auction House], [Sale Year].

Narrative Content: Use the auction house lot essays to provide descriptive, interesting details about technique and significance. It is okay to provide a longer, more detailed description for each painting rather than a long conclusion.

Constraints: * NO literature, bibliographies, or page numbers.

NO long lists of exhibitions; mention only the venue and year.

NO exhaustive provenance; mention only the most significant past owner.

Conclusion:

Heading: {artist_name}’s Market Legacy: An Enduring Ascent

Content: Analyze the turnover chart data from the provided data. Identify the "spike years" where volume peaked and anchor these claims to the specific dollar thresholds reached. Keep this conclusion small and concise.

Formatting:

No em-dashes.

Tone: Simple
"""
        return final_prompt
