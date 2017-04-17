from __future__ import print_function, division

import json
import os
import requests
import re

from . import Review
from app.dynamodb import dynamodb, utils
from app.steam.util import data_file
from bs4 import BeautifulSoup
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from decimal import Decimal
from datetime import datetime

reviews_re = re.compile(r"\(([0-9,]+) reviews?\)")
userscore_to_digit = {
    "Overwhelmingly Positive": 8,
    "Very Positive": 7,
    "Positive": 6,
    "Mostly Positive": 5,
    "Mixed": 4,
    "Mostly Negative": 3,
    "Negative": 2,
    "Very Negative": 1,
    "Overwhelmingly Negative": 0
}
digit_to_userscore = {score: r for r,score in userscore_to_digit.iteritems()}

class GameNotFoundException(Exception):
    def __init__(self, app_id):
        super(GameNotFoundException, self).__init__("Game %s does not exist!"%app_id)


class Game(object):
    table_name = "apps"
    table = dynamodb.Table(table_name)
    hash_key = ("app_id", utils.NUMBER)
    sorting_key = None

    @classmethod
    def create_table(cls):
        utils.create_dynamo_table(cls)

    @classmethod
    def get_from_steampsy(cls, app_id):
        game = requests.get("http://steamspy.com/api.php?request=appdetails&appid=%s"%app_id)
        return cls.from_steampspy_json(game)

    @classmethod
    def from_steampspy_json(cls, game):
        # We don't use any of these guys so we have to delete them
        game.pop("owners_variance", None)
        game.pop("players_forever", None)
        game.pop("players_forever_variance", None)
        game.pop("players_2weeks", None)
        game.pop("players_2weeks_variance", None)
        game.pop("average_forever", None)
        game.pop("average_2weeks", None)
        game.pop("median_forever", None)
        game.pop("median_2weeks", None)
        game.pop("ccu", None)

        game["app_id"] = int(game.pop("appid"))
        game["price"] = float(game["price"] or 0) / 100 # price is in cents

        if game["developer"] is None or len(game["developer"]) == 0:
            game["developer"] = None
        if game["publisher"] is None or len(game["publisher"]) == 0:
            game["publisher"] = None

        if len(game["tags"]) > 0 and isinstance(game["tags"], dict):
            tags = {k.lower().strip(): v for k, v in game["tags"].iteritems()}
        else:
            tags = dict()
        game["tags"] = tags

        # we have to set the actual userscore and num_reviews to -1 because this API doesn't return
        # those values
        game["userscore"] = None
        game["num_reviews"] = None

        if game["score_rank"] == "":
            game["score_rank"] = None
        else:
            game["score_rank"] = game["score_rank"]

        game["last_updated"] = datetime.now().date()
        return cls(**game)

    @classmethod
    def from_json(cls, game_json):
        game_json["last_updated"] = datetime.strptime(game_json["last_updated"], "%Y-%m-%d").date()
        return cls(**game_json)

    @classmethod
    def from_dynamo_json(cls, dynamo_json):
        dynamo_json["price"] = float(dynamo_json["price"])
        dynamo_json["tags"] = dynamo_json["tags"] or dict()
        return cls(**dynamo_json)

    @classmethod
    def batch_save(cls, games):
        return utils.batch_save(cls, games)

    @classmethod
    def find_by_name(cls, name):
        name_filter = Attr("name").eq(name)
        response = cls.table.scan(FilterExpression=name_filter)
        if "Item" in response:
            return cls.from_dynamo_json(response["Item"])
        else:
            return None

    @classmethod
    def get(cls, app_ids):
        if not (isinstance(app_ids) and len(app_ids) > 0):
            raise Exception("`app_ids` must be a non-empty set!")
        scanner = None
        for app_id in app_ids:
            if scanner is None:
                scanner = Key(cls.hash_key[0]).eq(app_id)
            else:
                scanner = scanner | Key(cls.hash_key[0]).eq(app_id)
        response = cls.table.scan(FilterExpression=scanner)
        results = dict()
        for item in response["Items"]:
            game = Game.from_dynamo_json(item)
            if game.userscore is None or (datetime.now().date() - game.last_updated).days >= 1:
                game.update_and_save()
            results[game.app_id] = game
        while "LastEvaluatedKey" in response:
            response = cls.table.scan(FilterExpression=scanner,
                                      ExclusiveStartKey=response['LastEvaluatedKey'])
            for item in response["Items"]:
                game = Game.from_dynamo_json(item)
                results[game.app_id] = game
        return results

    @classmethod
    def get_all(cls):
        response = cls.table.scan()
        results = map(cls.from_dynamo_json, response["Items"])
        while "LastEvaluatedKey" in response:
            response = cls.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            results += map(cls.from_dynamo_json, response["Items"])
        return results

    @classmethod
    def get_unscored(cls, limit=1000):
        attr_cond = Attr("userscore").eq(-1)
        response = cls.table.scan(FilterExpression=attr_cond, Limit=limit)
        results = map(cls.from_dynamo_json, response["Items"])
        while "LastEvaluatedKey" in response and len(results) < limit:
            response = cls.table.scan(FilterExpression=attr_cond,
                                      Limit=5,
                                      ExclusiveStartKey=response['LastEvaluatedKey'])
            results += map(cls.from_dynamo_json, response["Items"])
        return results


    def __init__(self, app_id, name, developer, publisher, owners, userscore, num_reviews,
                 score_rank, price, tags, last_updated):
        self.app_id = app_id
        self.name = name
        self.developer = developer
        self.publisher = publisher
        self.owners = owners
        self.userscore = userscore
        self.num_reviews = num_reviews
        self.score_rank = score_rank
        self.price = price
        self.tags = tags
        self.last_updated = last_updated
        self.steam_url = "http://store.steampowered.com/app/%s"%app_id

    def to_json(self):
        game_json = self.__dict__.copy()
        game_json["last_updated"] = self.last_updated.isoformat()
        game_json["tags"] = self.tags if len(self.tags) > 0 else None
        return game_json

    def to_dynamo_json(self):
        dynamo_json = self.to_json()
        dynamo_json["price"] = Decimal(str(self.price))
        return dynamo_json

    def save(self):
        Game.table.put_item(Item=self.to_dynamo_json())

    def fetch_more_reviews(self):
        Review.batch_save(Review.fetch_new_reviews(self.app_id))

    def get_saved_reviews(self, key_condition, filter_expression, max_items):
        primary_condition = Key(Review.hash_key).eq(self.app_id)
        if key_condition is not None:
            primary_condition = primary_condition & key_condition
        return Review.get(primary_condition, filter_expression, max_items)

    def get_recent_reviews(self, max_reviews=100):
        return self.get_saved_reviews(None, None, max_reviews)

    def update_and_save(self):
        game.update_steamspy_attributes()
        game.update_userscore()
        game.last_updated = datetime.now().date()
        game.save()

    def update_steamspy_attributes(self):
        new_game = Game.get_from_steampsy(self.app_id)
        self.name = new_game.name
        self.developer = new_game.developer
        self.publisher = new_game.publisher
        self.owners = new_game.owners
        self.userscore = new_game.userscore
        self.num_reviews = new_game.num_reviews
        self.score_rank = new_game.score_rank
        self.price = new_game.price
        self.tags = new_game.tags

    def update_userscore(self):
        page = requests.get("http://store.steampowered.com/app/%s"%self.app_id)
        soup = BeautifulSoup(page.text)

        summary_section = soup.find_all("div", class_="summary_section")
        for sec in summary_section:
            title, score, num_reviews = sec.stripped_strings
            if "overall" in title.lower():
                matches = reviews_re.match(num_reviews)
                if score in userscore_to_digit and matches is not None:
                    self.userscore = userscore_to_digit[score]
                    num_reviews, = matches.groups()
                    self.num_reviews = int(num_reviews.replace(",", ""))
                    print("Succesfully updated userscore for", self.app_id)
                    return

        # This is just so that we don't retry any games that can't be scored (maybe because they
        # haven't come out yet) automatically.
        print("Could not update userscore for", self.app_id)
        self.userscore = -2
        self.num_reviews = -2

def iter_all_games():
    games_json = requests.get("http://steamspy.com/api.php?request=all").json()
    for app_id, game in games_json.iteritems():
        if app_id == "999999":
            continue
        yield Game.from_steampspy_json(game)

if __name__ == '__main__':
    for u in Game.get_unscored(5):
        u.update_userscore()
