import os
import requests
import urllib.request

from fastapi import FastAPI, Request
from datetime import date, timedelta
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nba_api.stats.endpoints import scoreboardv2, leaguestandingsv3, boxscoretraditionalv3
from nba_api.stats.library.parameters import LeagueID
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

# url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + os.getenv('GEMINI_KEY') 
# myobj = {"contents": [{
#     "parts":[{"text": "Explain how AI works"}]
#     }]
#    }

# x = requests.post(url, json = myobj)

# print(x.text[""])

# from google import genai

# client = genai.Client(api_key=os.getenv('GEMINI_KEY'))

# response = client.models.generate_content(
#     model="gemini-2.0-pro-exp-02-05",
#     contents=["Sum up all 13th March 2025 NBA games."])
# print(response.text)


MAX_STATS = 10
MAX_STATS_EXTENDED = 20

def isEast(n):
    return n[6] == 'East'
def isWest(n):
    return n[6] == 'West'

standings = leaguestandingsv3.LeagueStandingsV3().get_dict()
standSets = standings['resultSets'][0]['rowSet']

eastStandings = list(filter(isEast, standSets))
westStandings = list(filter(isWest, standSets))

def get_scorers():

  today = date.today()
  yesterday = today - timedelta(days=1)

  scores = scoreboardv2.ScoreboardV2(league_id=LeagueID.nba,day_offset=0,game_date=yesterday)

  dico = scores.get_dict()

  rowSets = dico['resultSets'][1]['rowSet']

  gameIds = []

  for rs in enumerate(rowSets):
      gameIds.append(rs[1][2])

  uniqGamesIds = list(dict.fromkeys(gameIds))

  def get_boxscore(gameId):
      return boxscoretraditionalv3.BoxScoreTraditionalV3(gameId).get_dict()

  MAX_THREADS = min(os.cpu_count(), len(uniqGamesIds))
  with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
      games = list(executor.map(get_boxscore, uniqGamesIds))

  boxscores = []
  stats = []

  for game in games:
      boxscores.append(game['boxScoreTraditional']['homeTeam'])
      boxscores.append(game['boxScoreTraditional']['awayTeam'])

  for boxscore in boxscores:
    teamTricode = boxscore["teamTricode"]
    for player in boxscore['players']:
      player["teamTricode"] = teamTricode
      stats.append(player)

    rebounders = sorted(stats, key=lambda player: player['statistics']['reboundsTotal'], reverse=True)[:MAX_STATS]

  return {
     "scorers": sorted(stats, key=lambda player: player['statistics']['points'], reverse=True)[:MAX_STATS_EXTENDED],
     "rebounders": rebounders,
     "assisters": sorted(stats, key=lambda player: player['statistics']['assists'], reverse=True)[:MAX_STATS],
     "snipers": sorted(stats, key=lambda player: player['statistics']['threePointersPercentage'], reverse=True)[:MAX_STATS],
  }

app = FastAPI(title="NBA Night Recap", description="Recap of the NBA games of the night", version="0.1")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

statLeaders = get_scorers()

# @app.get("/check", response_class=JSONResponse)
# async def check():
#     return JSONResponse(content=check.get_status())

@app.get("/", response_class=HTMLResponse)
async def read_games(request: Request):
    today = date.today()
    yesterday = today - timedelta(days=1)

    scores = scoreboardv2.ScoreboardV2(league_id=LeagueID.nba,day_offset=0,game_date=yesterday)
    dico = scores.get_dict()

    rowSets = dico['resultSets'][1]['rowSet']

    games = []

    for index, rs in enumerate(rowSets):
        if index % 2 == 0:
            game = {}
            game['away'] = rs[5]
            game['home'] = rowSets[index + 1][5]

            awayQT3 = rs[8] + rs[9] + rs[10]
            homeQT3 = rowSets[index + 1][8] + rowSets[index + 1][9] + rowSets[index + 1][10]
            
            game['deltaQT3'] = abs(awayQT3 - homeQT3)
            games.append(game)

    games.sort(key=lambda x: x['deltaQT3'])

    return templates.TemplateResponse(request=request, name="index.html", context={
        "games": games,
        "statLeaders": statLeaders,
        "eastStandings": eastStandings,
        "westStandings": westStandings,
    })