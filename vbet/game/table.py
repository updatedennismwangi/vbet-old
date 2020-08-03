from typing import Dict, List
from operator import itemgetter
from .markets import Markets


class LeagueTable:
    def __init__(self, max_week):
        self.league = 0
        self.week = 1
        self.max_week = max_week
        self.results_pool: Dict = {}
        self.results_ids_pool: Dict = {}
        self.winning_ids_pool: Dict = {}
        self._table: List = []
        self.ready_table: List = []
        self.raw_table: Dict = {}
        self.event_block_map: Dict[int: int] = {}
        self.league_stats: Dict[int: Dict[int, Dict]] = {}

    @property
    def table(self):
        return self._table

    def on_event(self, league: int, week: int):
        if not self.league or self.league != league:
            self.clear_table()
            self.league = league
        self.week = week

    def is_empty(self):
        if self.event_block_map:
            return False
        return True

    def feed_result(self, e_block_id: int, league: int, week: int, results: Dict, results_ids: Dict, winning_ids: Dict):
        if not week:
            print(week)
        if league == self.league:
            self.event_block_map[week] = e_block_id
            self.results_pool[week] = results
            self.results_ids_pool[week] = results_ids
            self.winning_ids_pool[week] = winning_ids
            self.parse_week(week, results)
            self.get_league_table()

    def feed_stats(self, league: int, week: int, stats: Dict):
        self.league_stats[week] = stats

    def get_last_matches(self, team_id):
        return sorted(self.raw_table.get(team_id).items(), key=itemgetter(0), reverse=True)

    def get_min_block(self):
        if self.event_block_map:
            blocks = list(self.event_block_map.values())
            blocks.sort()
            return min(blocks)
        return

    def parse_week(self, week, week_data: Dict):
        for event in week_data.values():
            team_a = event.get('A')
            team_b = event.get('B')
            score = event.get('score')
            t = self.raw_table.get(team_a, {})
            s = self.raw_table.get(team_b, {})
            home = score[0]
            away = score[1]
            if home == away:
                x = 1
                y = 1
            elif home > away:
                x = 3
                y = 0
            else:
                x = 0
                y = 3
            t[week] = [x, home, away, team_b, 0]
            s[week] = [y, away, home, team_a, 1]
            self.raw_table[team_a] = t
            self.raw_table[team_b] = s

    def get_league_table(self):
        _table = {}
        for team, team_data in self.raw_table.items():
            points = 0
            gf = 0
            ga = 0
            streak = []
            if team_data:
                try:
                    week_values = sorted(team_data.items(), key=itemgetter(0))
                except TypeError as er:
                    print(team_data)
                    week_values = []
                for week_info in week_values:
                    week = week_info[0]
                    week_data = week_info[1]
                    p = week_data[0]
                    points += p
                    streak.append(p)
                    gf += week_data[1]
                    ga += week_data[2]
                _table[team] = {'team': team, 'pos': 0, 'points': points,
                                'gf': gf, 'ga': ga, 'gd': gf - ga, 'streak': streak}
        self.ready_table = _table
        # Sort
        data = [_ for _ in _table.values()]
        i = 0
        while i < len(data):
            o = 0
            while o < len(data):
                data_1 = data[i]
                data_2 = data[o]
                points_1 = data_1['points']
                points_2 = data_2['points']
                if points_2 < points_1:
                    data[i] = data_2
                    data[o] = data_1
                elif points_1 == points_2:
                    gd_1 = data_1['gd']
                    gd_2 = data_2['gd']
                    if gd_2 > gd_1:
                        data[i] = data_2
                        data[o] = data_1
                o += 1
            i += 1
        for pos, team_data in enumerate(data):
            team_data['pos'] = pos + 1
        _table = {}
        for td in data:
            _table[td.get('team')] = td
        self.ready_table = _table
        self._table = data

    def clear_table(self):
        self.results_pool = {}
        self.results_ids_pool = {}
        self.winning_ids_pool = {}
        self._table = []
        self.raw_table = {}
        self.ready_table = {}
        self.event_block_map = {}
        self.league_stats = {}

    def get_raw_team_data(self, team):
        return self.raw_table.get(team, None)

    def get_missing_weeks(self):
        pool_weeks = set(self.event_block_map.keys())
        all_weeks = set([i for i in range(1, self.week)])
        missing = list(all_weeks - pool_weeks)
        return missing

    def is_complete(self):
        return len(self.event_block_map) == self.max_week

    def get_week_results(self, week_id: int):
        return self.results_pool.get(week_id, {})

    def get_week_stats(self, week_id: int):
        return self.league_stats.get(week_id, {})

    def check_weeks(self, weeks: List[int]):
        not_ready = []
        for week in weeks:
            if week not in self.event_block_map:
                not_ready.append(week)
        return not_ready
