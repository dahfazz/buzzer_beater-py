
import os
from datetime import date, timedelta
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.endpoints import boxscoretraditionalv3
from nba_api.stats.library.parameters import LeagueID

from concurrent.futures import ThreadPoolExecutor

def get_scorers():

  today = date.today()
  yesterday = today - timedelta(days=1)

  scores = scoreboardv2.ScoreboardV2(league_id=LeagueID.nba,day_offset=0,game_date=yesterday)

  dico = scores.get_dict()

  rowSets = dico['resultSets'][1]['rowSet']

  gameIds = []
  gameStats = []
  playerStats = []

  for rs in enumerate(rowSets):
      gameIds.append(rs[1][2])

  uniqGamesIds = list(dict.fromkeys(gameIds))

  def get_boxscore(gameId):
      return boxscoretraditionalv3.BoxScoreTraditionalV3(gameId).get_dict()

  MAX_THREADS = min(os.cpu_count(), len(uniqGamesIds))
  with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
      games = list(executor.map(get_boxscore, uniqGamesIds))

  boxscores = []
  scorers = []

  for game in games:
      boxscores.append(game['boxScoreTraditional']['homeTeam'])
      boxscores.append(game['boxScoreTraditional']['awayTeam'])

  for boxscore in boxscores:
    for player in boxscore['players']:
      scorers.append({
        "firstName": player['firstName'],
        "familyName": player['familyName'],
        "points": player['statistics']['points'],
      })

  def sortFn(player):
    return player['points']

  scorers.sort(key=sortFn, reverse=True)


  return scorers[:10]
