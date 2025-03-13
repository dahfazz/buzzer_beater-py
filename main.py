import os
from fastapi import FastAPI, Request
from datetime import date, timedelta
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.endpoints import boxscoretraditionalv3
from nba_api.stats.library.parameters import LeagueID
from concurrent.futures import ThreadPoolExecutor

MAX_STATS = 10
MAX_STATS_EXTENDED = 20

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
        "statLeaders": statLeaders
    })