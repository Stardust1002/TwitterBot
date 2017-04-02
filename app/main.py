import logging
import re
import tweepy
import redis

from datetime import datetime
from random import randint
from time import gmtime
from time import sleep
from time import strftime
from os import environ

auth_keys = (environ['auth1'], environ['auth2'])
auth_tokens = (environ['token1'], environ['token2'])
auth_redis = environ['redis']

auth = tweepy.OAuthHandler(*auth_keys)
auth.set_access_token(*auth_tokens)
api = tweepy.API(auth)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    filename='app/logs/{}.log'.format(strftime("%Y-%m-%d", gmtime())),
                    filemode='a')
logger = logging.getLogger('Twitter_bot')
logger.addHandler(logging.StreamHandler())

politics = ('JLMelenchon', 'benoithamon', 'EmmanuelMacron')
teams = ('NHLBlackhawks', 'PSG_inside', 'RCLens', 'chicagobulls')
games = ('NintendoFrance', 'PlayStationFR', 'Gamekult', 'zqsdfr', 'JVlemag')
geek = ('nextinpact', 'Hitekfr', 'lesnums', 'newsycombinator')
companies = ('IpponUSA', 'Google', 'utc_compiegne', 'NASA', 'starwars', 'CERN', 'TeslaMotors', 'SpaceX')
people = ('boutangyann', 'Snowden', 'BernieSanders', 'realDonaldTrump', 'tim_cook', 'elonmusk', 'Thom_astro', 'HamillHimself')
news = ('CourrierPicard', 'lemondefr', 'konbini', 'LeHuffPost', 'mediapart', 'wikileaks', 'newscientist')
photos = ('HUBBLE_space', 'Fascinatingpics', 'BEAUTIFULPlCS')

class DB:
    pool = None
    instance = None
    pipeline = None

    def __init__(self, connectionPool):
        DB.pool = connectionPool
        DB.instance = redis.Redis(connection_pool=DB.pool)
        DB.pipeline = DB.instance.pipeline()

    @staticmethod
    def connect(connectionPool=None):
        if connectionPool is None:
            DB.instance = redis.Redis(connection_pool=DB.pool)
        else:
            DB.instance = redis.Redis(connection_pool=connectionPool)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            DB.pipeline.execute()
            logger.info("Redis Pipeline executed")
        except Exception as ex:
            logger.error("Redis Pipeline execution failed")
            logger.error(str(ex))

def getRootTweet(tweet):
    return getRootTweet(tweet.retweeted_status) if hasattr(tweet, 'retweeted_status') else tweet

def checkSeriousness(tweet, limit=20000):
    return tweet.author.followers_count >= limit

def retweet(tweet):
    try:
        tweet.retweet()
        logger.info("Retweeted {}".format(tweet.text[0:min(len(tweet.text), 20)]))
        return True
    except Exception as exc:
        logger.info("Retweet Failed {} {} {}".format(tweet.text[0:min(len(tweet.text), 20)], type(exc), exc))
    return False

def favorite(tweet):
    try:
        tweet.favorite()
        logger.info("Liked {}".format(tweet.text[0:min(len(tweet.text), 20)]))
        return True
    except Exception as exc:
        logger.info("Like Failed {}".format(tweet.text[0:min(len(tweet.text), 20)], type(exc), exc))
    return False

def followUser(user):
    try:
        user.follow()
        logger.info("Now following {} @ {}".format(user.screen_name, user.id_str))
    except:
        logger.info("Following Failed {} @ {} ".format(user.screen_name, user.id_str))
        pass

def follow(tweet):
    followUser(tweet.author)
    return tweet

def deepFollow(tweet):
    follow(tweet)
    for x in re.findall('@(\S+)', tweet.text):
        try:
            followUser(api.get_user(x))
        except:
            pass
    return tweet

def anyTermsInTweet(terms: list, tweet:tweepy.models.Status) -> bool:
    return len([1 for x in terms if x.lower() in tweet.text.lower()]) > 0

def allTermsInTweet(terms: list, tweet:tweepy.models.Status) -> bool:
    return len([0 for x in terms if x.lower() in tweet.text.lower()]) == len(terms)

def getPostsContaining(queries, tweets, flag='any') -> list:
    if flag == 'any':
        return [tweet for tweet in tweets if anyTermsInTweet(queries, tweet)]
    else:
        return [tweet for tweet in tweets if allTermsInTweet(queries, tweet)]

def getLastPostId(queries: list, tweets, flag='any') -> int:
    try:
        return sorted([tweet.id for tweet in getPostsContaining(queries, tweets, flag)], reverse=True)[0]
    except Exception as exc:
        return 840978208107425793

def flush(queries, flag='any'):
    try:
        while True:
            tweets = getPostsContaining(queries, api.user_timeline(count=100), flag)
            for tweet in tweets:
                api.destroy_status(tweet.id)
            logger.info("Flushed {} tweets from profile containing {}".format(len(tweets), queries))
            if len(tweets) == 0:
                break
    except:
        pass

def scenarioConcours(limit=100):
    results1 = api.search(q="#concours",
                                  result_type='mixed',
                                  count=limit)
    results2 = api.search(q="#jeu",
                                  result_type='mixed',
                                  count=limit)
    results3 = api.search(q="#jeuconcours",
                                  result_type='mixed',
                                  count=limit)
    #since_id = getLastPostId(['concours'], api.user_timeline(), 'any')
    results = map(getRootTweet, results1+results2+results3)
    results = filter(checkSeriousness, results)
    results = filter(lambda x: allTermsInTweet(["follow","rt"], x), results)
    results = filter(lambda x: DB.instance.sadd(x.author.screen_name, x.id), results)

    to_retweet = map(deepFollow, results)
    results = []
    for result in to_retweet:
        results.append(retweet(result))
        sleep(randint(1, 20))
    return results

def getAllTweetsFrom(user: str) -> list:
    res = []
    for _ in range(100):
        print(_, ".",end="")
        try:
            if _ == 0:
                r = api.user_timeline(user, count=100)
            else:
                r = api.user_timeline(user, count=100, max_id=res[-1].id)
            res += r
            sleep(0.5)
        except:
            break
    return res

def addProfileToCache(user: str) -> list:
    tweets = [getRootTweet(tweet) for tweet in getAllTweetsFrom(user)]
    for tweet in tweets: DB.pipeline.sadd(tweet.author.screen_name, tweet.id)
    return DB.pipeline.execute()

def scenarioUser(liste, likeRatio=3, retweetRatio=8):
    flagged = False
    liste = list(liste)
    while not flagged and liste:
        choice = liste[randint(0, len(liste) - 1)]
        user = api.get_user(choice)
        status = user.status
        if DB.instance.sadd(user.screen_name, status.id):
            if randint(0,10) < retweetRatio and status.retweet_count > 50:
                flagged = retweet(status)
            if randint(0, 10) < likeRatio and status.favorite_count > 50:
                flagged = flagged or favorite(status)
        liste = liste.remove(choice)
    if flagged:
        sleep(randint(60, 300))

def job():
    if datetime.now().hour >= randint(7, 9):
        logger.info('- Concours:')
        scenarioConcours(30)
        logger.info('- Politics:')
        scenarioUser(politics, likeRatio=3, retweetRatio=7)
        logger.info('- Teams:')
        scenarioUser(teams, likeRatio=8, retweetRatio=3)
        logger.info('- Games:')
        scenarioUser(games, likeRatio=5, retweetRatio=7)
        logger.info('- Geek:')
        scenarioUser(geek, likeRatio=2, retweetRatio=8)
        logger.info('- Companies:')
        scenarioUser(companies, likeRatio=6, retweetRatio=5)
        logger.info('- People:')
        scenarioUser(people, likeRatio=8, retweetRatio=7)
        logger.info('- News:')
        scenarioUser(news, likeRatio=1, retweetRatio=6)
        logger.info('- Photos:')
        scenarioUser(photos, likeRatio=8, retweetRatio=5)

if __name__ == "__main__":
    with DB(redis.ConnectionPool(password=auth_redis, host='127.0.0.1', port=6379, db=0)):
        logger.info("# Tweets from profile added to cache:", sum(addProfileToCache("TonyJean42")))
        while True:
            logger.info("=========== New job starting on {} =========".format(datetime.now()))
            job()
            logger.info("=========== Job paused =============")
            sleep(randint(60, 600))