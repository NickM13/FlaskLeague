import pymongo
from ssh_pymongo import MongoSession
from flask import Flask, current_app, request, render_template
from flask_paginate import Pagination
import math
import operator
import os

app = Flask(__name__)
app.config.from_pyfile("main.cfg")

mongo = MongoSession(
	host=os.getenv("MONGOSSH"),
	port=22,
	user='dev',
	key=os.getenv("MONGOKEY"),
	to_port=27017,
	to_host='localhost'
).connection


def get_collection(db, collection):
	return mongo[db][collection]


def find_one(db, collection, query):
	return get_collection(db, collection).find_one(query)


def find_many(db, collection, query, key_or_list, skip, limit):
	collection = get_collection(db, collection)
	cursor = collection.find(query).sort(key_or_list).skip(skip).limit(limit)

	docs = []
	for doc in cursor:
		docs.append(doc)

	return [docs, collection.count_documents(query)]


def get_per_page():
	return current_app.config.get("PER_PAGE")


def get_page_info(count, page):
	max_page = math.ceil(count / get_per_page())
	page = bound(1, max_page, page)
	return max_page, page, (page - 1) * get_per_page()


def get_leaderboard_page_info(plugin, gamemode, page):
	lb = find_one("SpleefLeague", "Leaderboards", {"name": "%s:%s" % (plugin, gamemode)})

	if lb:
		player_docs = lb["players"]
		unsorted_players = []
		for entry in player_docs.values():
			player = {
				"username": entry['username'],
				"elo": int(entry['elo'])
			}
			unsorted_players.append(player)

		sorted_players = sorted(unsorted_players, key=operator.itemgetter('elo'), reverse=True)

		max_page, page, counter = get_page_info(len(sorted_players), page)

		entries = []
		for player in sorted_players[counter:counter + get_per_page():1]:
			counter += 1

			entries.append([counter, player['username'], player['elo']])

		return {"total": len(player_docs), "entries": entries, "page": page, "max_page": max_page}
	else:
		return None


def get_all_players_info(page: int):
	player_docs, player_count = find_many("SpleefLeague", "Players", {"purse.currencies.COIN": {"$exists": True}}, [("lastOnline", pymongo.DESCENDING), ("username", pymongo.ASCENDING)], (page - 1) * get_per_page(),
	                                      get_per_page())
	max_page, page, counter = get_page_info(player_count, page)

	entries = []
	for player in player_docs:
		counter += 1

		#if player['purse']['currencies']:
		entries.append([counter, player['username'], player['permRank']['rankName']])

	return {"total": player_count, "entries": entries, "page": page, "max_page": max_page}


def bound(lower, higher, value):
	return max(lower, min(higher, value))


@app.route("/players", defaults={"page": 1})
@app.route("/players/<int:page>")
def players(page):
	page = page if page else (request.args.get("page", 1, int))

	info = get_all_players_info(page)

	headers = ["#", "Player Name", "Rank", "Currency"]

	pagination = get_pagination(
		page=page,
		per_page=get_per_page(),
		total=info["total"],
		record_name="players",
		format_total=True,
		format_number=True
	)

	return render_template(
		"index.html",
		listname="Players",
		headers=headers,
		entries=info["entries"],
		pagination=pagination,
		active_url="leaderboards-page-url"
	)


@app.route("/leaderboard", defaults={"page": 1})
@app.route("/leaderboard/<int:page>")
def leaderboards(page):
	plugin = request.args.get("plugin", "spleef", str)
	gamemode = request.args.get("gamemode", "classic", str)
	page = page if page else (request.args.get("page", 1, int))

	info = get_leaderboard_page_info(plugin, gamemode, page)

	headers = ["#", "Player Name", "Elo"]

	pagination = get_pagination(
		page=page,
		per_page=get_per_page(),
		total=info["total"],
		record_name="players",
		format_total=True,
		format_number=True
	)

	return render_template(
		"index.html",
		headers=headers,
		entries=info["entries"],
		pagination=pagination,
		active_url="leaderboards-page-url"
	)


@app.route("/")
def index():
	plugin = request.args.get("plugin", "spleef", str)
	gamemode = request.args.get("gamemode", "classic", str)
	page = request.args.get("page", 1, int)

	info = get_leaderboard_page_info(plugin, gamemode, page)

	headers = ["#", "Player Name", "Elo"]

	pagination = get_pagination(
		p=page,
		pp=get_per_page(),
		total=info["total"],
		record_name="users",
		format_total=True,
		format_number=True,
		page_parameter="p",
		per_page_parameter="pp",
	)

	return render_template(
		"index.html",
		headers=headers,
		entries=info["entries"],
		pagination=pagination
	)


def get_css_framework():
	css = request.args.get("bs")
	if css:
		return css

	return current_app.config.get("CSS_FRAMEWORK", "bootstrap5")


def get_link_size():
	return current_app.config.get("LINK_SIZE", "")


def get_alignment():
	return current_app.config.get("LINK_ALIGNMENT", "")


def show_single_page_or_not():
	return current_app.config.get("SHOW_SINGLE_PAGE", False)


def get_pagination(**kwargs):
	kwargs.setdefault("record_name", "records")
	return Pagination(
		css_framework=get_css_framework(),
		link_size=get_link_size(),
		alignment=get_alignment(),
		show_single_page=show_single_page_or_not(),
		**kwargs
	)


if __name__ == '__main__':
	app.run(debug=True)
