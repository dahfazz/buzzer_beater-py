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

MAX_STATS = 10
MAX_STATS_EXTENDED = 20

def isEast(n):
    return n[6] == 'East'

def isWest(n):
    return n[6] == 'West'

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

      astPerf = int(player['statistics']['assists']) + int(player['statistics']['points'])
      rebPerf = int(player['statistics']['reboundsTotal']) + int(player['statistics']['points'])
      player["perf"] = astPerf if astPerf > rebPerf else rebPerf
      player["perfLabel"] = "ASTPTS" if astPerf > rebPerf else "REBPTS"

      stats.append(player)



    rebounders = sorted(stats, key=lambda player: player['statistics']['reboundsTotal'], reverse=True)[:MAX_STATS]

  return {
     "performers": sorted(stats, key=lambda player: player['perf'], reverse=True)[:MAX_STATS_EXTENDED],
     "scorers": sorted(stats, key=lambda player: player['statistics']['points'], reverse=True)[:MAX_STATS_EXTENDED],
     "rebounders": rebounders,
     "assisters": sorted(stats, key=lambda player: player['statistics']['assists'], reverse=True)[:MAX_STATS],
     "snipers": sorted(stats, key=lambda player: player['statistics']['threePointersPercentage'], reverse=True)[:MAX_STATS],
  }

def get_standings():
    standings = leaguestandingsv3.LeagueStandingsV3().get_dict()
    standSets = standings['resultSets'][0]['rowSet']

    pos_series = sorted(list(filter(lambda team: int(team[36]) >= 0, standSets)), key=lambda team: team[37], reverse=True)
    neg_series = sorted(list(filter(lambda team: int(team[36]) < 0, standSets)), key=lambda team: team[37], reverse=False)

    return {
        "eastStandings": list(filter(isEast, standSets)),
        "westStandings": list(filter(isWest, standSets)),
        "hots": pos_series + neg_series,
    }

app = FastAPI(title="NBA Night Recap", version="0.1")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

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
        "statLeaders": get_scorers(),
        "eastStandings": get_standings()["eastStandings"],
        "westStandings": get_standings()["westStandings"],
        "hots": get_standings()["hots"],
    })