#!/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import random
import codecs
import hashlib
import requests
import urllib.parse
import json
import re
import time
import configparser
from statistics import mean
from urllib3 import util
from datetime import datetime
from logging import getLogger, FileHandler, Formatter
from collections import deque
from elasticsearch import Elasticsearch

# Printing colors.
OK_BLUE = '\033[94m'      # [*]
NOTE_GREEN = '\033[92m'   # [+]
FAIL_RED = '\033[91m'     # [-]
WARN_YELLOW = '\033[93m'  # [!]
ENDC = '\033[0m'
PRINT_OK = OK_BLUE + '[*]' + ENDC
PRINT_NOTE = NOTE_GREEN + '[+]' + ENDC
PRINT_FAIL = FAIL_RED + '[-]' + ENDC
PRINT_WARN = WARN_YELLOW + '[!]' + ENDC

# Type of printing.
OK = 'ok'         # [*]
NOTE = 'note'     # [+]
FAIL = 'fail'     # [-]
WARNING = 'warn'  # [!]
NONE = 'none'     # No label.


# Utility class.
class Utilty:
    def __init__(self, team_name, sql=None, debug=False, english=False):
        self.file_name = os.path.basename(__file__)
        self.full_path = os.path.dirname(os.path.abspath(__file__))

        # Read config.ini.
        full_path = os.path.dirname(os.path.abspath(__file__))
        config = configparser.ConfigParser()
        config.read(os.path.join(full_path, 'config.ini'), encoding='utf-8')

        try:
            self.team_name = team_name
            self.player_id = 'Base'
            self.sql = sql
            self.banner_delay = float(config['Common']['banner_delay'])
            self.loop_delay_rate = int(config['Common']['loop_delay_rate'])
            self.loop_delay_rate_corporate = int(config['Common']['loop_delay_rate_corporate'])
            self.busy_period_rate = int(config['Common']['busy_period_rate'])
            self.epoch_delay_time = float(config['Common']['epoch_delay_time'])
            self.corporate_delay_time = float(config['Common']['corporate_delay_time'])
            self.con_timeout = float(config['Common']['con_timeout'])
            self.report_date_format = config['Common']['date_format']
            self.log_name = config['Common']['log_name']
            self.log_dir = os.path.join(full_path, config['Common']['log_path'])
            self.log_file = config['Common']['log_file'].format(team_name)
            self.log_path = os.path.join(self.log_dir, self.log_file)
            if os.path.exists(self.log_dir) is False:
                os.mkdir(self.log_dir)
            self.modules_dir = config['Common']['module_path']
            self.ua = config['Common']['user-agent']
            self.proxy_addr = config['Common']['proxy_addr']
            self.proxy_user = config['Common']['proxy_user']
            self.proxy_pass = config['Common']['proxy_pass']
            self.encoding = config['Common']['default_encoding']
            self.docker_host = config['Common']['docker_host'].format(team_name)
            self.cookie_param = config['Common']['cookie_name']
            self.max_player_num = int(config['Common']['max_player_num'])
            self.max_player_level = int(config['Common']['max_player_level'])
            self.current_user_num = 0
            self.recovery_gold = int(config['Common']['recovery_gold'])
            self.min_gatya_gold = int(config['Common']['min_gatya_gold'])
            self.std_gatya_gold = int(config['Common']['std_gatya_gold'])
            self.stamina_charge_price = int(config['Common']['stamina_charge_price'])
            self.gatya_charge_price = int(config['Common']['gatya_charge_price'])
            self.gatya_rate = int(config['Common']['gatya_rate'])
            self.standard_stamina = float(config['Common']['standard_stamina'])
            self.max_injustice_num = int(config['Common']['max_injustice_num'])
            self.penalty_time_coef = int(config['Common']['penalty_time_coef'])
            self.cheat_penalty_time_coef = int(config['Common']['cheat_penalty_time_coef'])
            self.max_stamina_loop_num = int(config['Common']['max_stamina_loop'])
            self.max_course_loop_num = int(config['Common']['max_course_loop'])
            self.max_battle_loop_num = int(config['Common']['max_battle_loop'])
            self.battle_stamina_rate = float(config['Common']['battle_stamina_rate'])
            self.max_gatya_loop_num = int(config['Common']['max_gatya_loop'])
            self.loop_wait_time = float(config['Common']['loop_wait_time'])
            self.sr_check_count = int(config['Common']['sr_check_count'])
            self.user_list = {}
            self.competition_start_time = config['Common']['competition_start_time']
            self.competition_lunch_time = config['Common']['competition_lunch_time']
            self.competition_restart_time = config['Common']['competition_restart_time']
            self.competition_busy_time = config['Common']['competition_busy_time']
            self.competition_end_time = config['Common']['competition_end_time']
            self.sr_queue = deque([False, False, False])

            # Gatya rate: 100% -> 1, 50% -> 2, 30% -> 3, 20% -> 5, 10% -> 8, 0% -> 11
            if self.gatya_rate in [1, 2, 3, 5, 8, 11]:
                self.print_message(OK, 'Gatya rate: "{}".'.format(self.gatya_rate))
            else:
                self.print_message(WARNING, 'Invalid Gatya rate {}. Forcibly set 5 (20%).'.format(self.gatya_rate))
                self.gatya_rate = 5

            # API: Ranking information.
            self.api_ranking_method = config['API_Ranking']['method']
            self.api_ranking_ctype = config['API_Ranking']['content-type']
            if debug:
                self.api_ranking_url = config['API_Ranking']['url_debug']
            else:
                self.api_ranking_url = config['API_Ranking']['url'].format(self.docker_host)

            # API: New User.
            self.api_new_user_method = config['API_NewUser']['method']
            self.api_new_user_ctype = config['API_NewUser']['content-type']
            if debug:
                self.api_new_user_url = config['API_NewUser']['url_debug']
            else:
                self.api_new_user_url = config['API_NewUser']['url'].format(self.docker_host)
            self.api_new_user_params = {}
            for param in str(config['API_NewUser']['params']).split('@'):
                self.api_new_user_params[param] = ''

            # API: Login.
            self.api_login_method = config['API_Login']['method']
            self.api_login_ctype = config['API_Login']['content-type']
            if debug:
                self.api_login_url = config['API_Login']['url_debug']
            else:
                self.api_login_url = config['API_Login']['url'].format(self.docker_host)
            self.api_login_params = {}
            for param in str(config['API_Login']['params']).split('@'):
                self.api_login_params[param] = ''

            # API: Get UserId.
            self.api_get_userid_method = config['API_GetUserId']['method']
            self.api_get_userid_ctype = config['API_GetUserId']['content-type']
            if debug:
                self.api_get_userid_url = config['API_GetUserId']['url_debug']
            else:
                self.api_get_userid_url = config['API_GetUserId']['url'].format(self.docker_host)

            # API: Upload.
            self.api_upload_method = config['API_Upload']['method']
            self.api_upload_ctype = config['API_Upload']['content-type']
            if debug:
                self.api_upload_url = config['API_Upload']['url_debug']
            else:
                self.api_upload_url = config['API_Upload']['url'].format(self.docker_host)
            self.api_upload_params = {}
            for param in str(config['API_Upload']['params']).split('@'):
                self.api_upload_params[param] = ''

            # API: Delete.
            self.api_delete_method = config['API_Delete']['method']
            self.api_delete_ctype = config['API_Delete']['content-type']
            if debug:
                self.api_delete_url = config['API_Delete']['url_debug']
            else:
                self.api_delete_url = config['API_Delete']['url'].format(self.docker_host)

            # API: GetCourse.
            self.api_get_course_method = config['API_Course']['method']
            self.api_get_course_ctype = config['API_Course']['content-type']
            if debug:
                self.api_get_course_url = config['API_Course']['url_debug']
            else:
                self.api_get_course_url = config['API_Course']['url'].format(self.docker_host)

            # API: CoursePost.
            self.api_post_course_method = config['API_CoursePost']['method']
            self.api_post_course_ctype = config['API_CoursePost']['content-type']
            if debug:
                self.api_post_course_url = config['API_CoursePost']['url_debug']
            else:
                self.api_post_course_url = config['API_CoursePost']['url'].format(self.docker_host)
            self.api_post_course_params = {}
            for param in str(config['API_CoursePost']['params']).split('@'):
                self.api_post_course_params[param] = ''

            # API: Battle.
            self.api_battle_method = config['API_Battle']['method']
            self.api_battle_ctype = config['API_Battle']['content-type']
            if debug:
                self.api_battle_url = config['API_Battle']['url_debug']
            else:
                self.api_battle_url = config['API_Battle']['url'].format(self.docker_host)

            # API: Recovery.
            self.api_recovery_method = config['API_Recovery']['method']
            self.api_recovery_ctype = config['API_Recovery']['content-type']
            if debug:
                self.api_recovery_url = config['API_Recovery']['url_debug']
            else:
                self.api_recovery_url = config['API_Recovery']['url'].format(self.docker_host)
            self.api_recovery_params = {}
            for param in str(config['API_Recovery']['params']).split('@'):
                self.api_recovery_params[param] = ''

            # API: Gatya.
            self.api_gatya_method = config['API_Gatya']['method']
            self.api_gatya_ctype = config['API_Gatya']['content-type']
            if debug:
                self.api_gatya_url = config['API_Gatya']['url_debug']
            else:
                self.api_gatya_url = config['API_Gatya']['url'].format(self.docker_host)
            self.api_gatya_params = {}
            for param in str(config['API_Gatya']['params']).split('@'):
                self.api_gatya_params[param] = ''

            # API: Player.
            self.api_player_method = config['API_Player']['method']
            self.api_player_ctype = config['API_Player']['content-type']
            if debug:
                self.api_player_url = config['API_Player']['url_debug']
            else:
                self.api_player_url = config['API_Player']['url'].format(self.docker_host)

            # API: Charge.
            self.api_charge_method = config['API_Charge']['method']
            self.api_charge_ctype = config['API_Charge']['content-type']
            if debug:
                self.api_charge_url = config['API_Charge']['url_debug']
            else:
                self.api_charge_url = config['API_Charge']['url'].format(self.docker_host)
            self.api_charge_params = {}
            for param in str(config['API_Charge']['params']).split('@'):
                self.api_charge_params[param] = ''

            # Game Top.
            self.api_game_top_method = config['API_GameTop']['method']
            self.api_game_top_ctype = config['API_GameTop']['content-type']
            if debug:
                self.api_game_top_url = config['API_GameTop']['url_debug']
            else:
                self.api_game_top_url = config['API_GameTop']['url'].format(self.docker_host)

            # Web site.
            self.web_host = config['Common']['web_host'].format(team_name)
            if english:
                self.corp_categories = str(config['Common']['corp_categories_en']).split('@')
            else:
                self.corp_categories = str(config['Common']['corp_categories']).split('@')
            self.regex_hacked = config['Common']['hacked_string']
            self.regex_warning = config['Common']['warning_string']
            # URL.
            if debug:
                self.web_corporate_url = config['WEB_Corporate']['url_debug']
                self.web_fansite_url = config['WEB_FanSite']['url_debug']
                self.web_inquiry_url = config['WEB_INQUIRY']['url_debug']
                if english:
                    # English version (kendit, not exist "saiyo").
                    self.web_bbs_url = config['WEB_BBS']['url_debug_en']
                else:
                    # Japanese version.
                    self.web_saiyo_url = config['WEB_Saiyo']['url_debug']
                    self.web_bbs_url = config['WEB_BBS']['url_debug']
            elif english:
                self.web_corporate_url = config['WEB_Corporate']['url'].format(self.web_host)
                self.web_fansite_url = config['WEB_FanSite']['url'].format(self.web_host)
                self.web_bbs_url = config['WEB_BBS']['url_en'].format(self.web_host)
                self.web_inquiry_url = config['WEB_INQUIRY']['url'].format(self.web_host)
            else:
                self.web_corporate_url = config['WEB_Corporate']['url'].format(self.web_host)
                self.web_fansite_url = config['WEB_FanSite']['url'].format(self.web_host)
                self.web_saiyo_url = config['WEB_Saiyo']['url'].format(self.web_host)
                self.web_bbs_url = config['WEB_BBS']['url'].format(self.web_host)
                self.web_inquiry_url = config['WEB_INQUIRY']['url'].format(self.web_host)

            # Score.
            self.web_corporate_score = int(config['WEB_Corporate']['score'])
            self.web_fansite_score = int(config['WEB_FanSite']['score'])
            self.web_saiyo_score = int(config['WEB_Saiyo']['score'])
            self.web_bbs_score = int(config['WEB_BBS']['score'])
            self.web_inquiry_score = int(config['WEB_INQUIRY']['score'])

            # Hacked regex.
            self.regex_web_hacked = config['Common']['hacked_string']
            self.regex_web_warning = config['Common']['warning_string']

            # Keyword.
            if english:
                self.web_corporate_keywords = config['WEB_Corporate']['keywords_en'].split('@')
                self.web_fansite_keywords = config['WEB_FanSite']['keywords_en'].split('@')
                self.web_bbs_keywords = config['WEB_BBS']['keywords_en'].split('@')
                self.web_inquiry_keywords = config['WEB_INQUIRY']['keywords_en'].split('@')
            else:
                self.web_corporate_keywords = config['WEB_Corporate']['keywords'].split('@')
                self.web_fansite_keywords = config['WEB_FanSite']['keywords'].split('@')
                self.web_saiyo_keywords = config['WEB_Saiyo']['keywords'].split('@')
                self.web_bbs_keywords = config['WEB_BBS']['keywords'].split('@')
                self.web_inquiry_keywords = config['WEB_INQUIRY']['keywords'].split('@')

            # Repository server.
            self.repo_url_hash = config['REPO_SRV']['repo_url_hash']
            if debug:
                self.repo_url_readme = config['REPO_SRV']['url_readme_debug']
                self.repo_url_csv = config['REPO_SRV']['url_csv_debug']
            else:
                self.repo_url_readme = config['REPO_SRV']['url_readme'].format(team_name, self.repo_url_hash)
                self.repo_url_csv = config['REPO_SRV']['url_csv'].format(team_name, self.repo_url_hash)
            self.repo_score = int(config['REPO_SRV']['score'])
            self.repo_interval = int(config['REPO_SRV']['check_interval'])
            self.repo_hash_file = config['REPO_SRV']['repo_hash_file']
            self.repo_regex_hacked = config['REPO_SRV']['hacked_string']

            # Define Elasticsearch information (Score server).
            if debug:
                elastic_host = config['Common']['elastic_host_debug']
            else:
                elastic_host = config['Common']['elastic_host']
            elastic_port = int(config['Common']['elastic_port'])
            self.elastic_index_sc = config['Common']['elastic_index_sc']
            self.elastic_doc_score = config['Common']['elastic_doc_score']
            self.elastic_index_ch = config['Common']['elastic_index_ch']
            self.elastic_doc_charge = config['Common']['elastic_doc_charge']
            self.es = Elasticsearch('{}:{}'.format(elastic_host, elastic_port))

            # Create index for score.
            if self.es.indices.exists(index=self.elastic_index_sc):
                self.print_message(WARNING, 'Index "{}" is existing.'.format(self.elastic_index_sc))
                self.print_message(WARNING, 'Could not create index "{}".'.format(self.elastic_index_sc))
            else:
                settings_json_sc = config['Common']['elastic_settings_sc']
                with codecs.open(os.path.join(full_path, settings_json_sc), 'r', 'utf-8') as fin:
                    mapping = json.loads(fin.read().replace('\0', ''))
                    self.es.indices.create(index=self.elastic_index_sc, body=mapping)
                self.print_message(WARNING, 'Created new index : {}'.format(self.elastic_index_sc))

            # Create index for charge.
            if self.es.indices.exists(index=self.elastic_index_ch):
                self.print_message(WARNING, 'Index "{}" is existing.'.format(self.elastic_index_ch))
                self.print_message(WARNING, 'Could not create index "{}".'.format(self.elastic_index_ch))
            else:
                settings_json_ch = config['Common']['elastic_settings_ch']
                with codecs.open(os.path.join(full_path, settings_json_ch), 'r', 'utf-8') as fin:
                    mapping = json.loads(fin.read().replace('\0', ''))
                    self.es.indices.create(index=self.elastic_index_ch, body=mapping)
                self.print_message(WARNING, 'Created new index : {}'.format(self.elastic_index_ch))
        except Exception as e:
            self.print_message(FAIL, 'Reading config.ini is failure : {}'.format(e))
            sys.exit(1)

        # Initialize http session object.
        self.session = None

        # Set proxy server.
        if self.proxy_addr != '':
            parse_obj = util.parse_url(self.proxy_addr)
            if self.proxy_user != '':
                self.proxy = {parse_obj.scheme: parse_obj.scheme + '://' +
                                                self.proxy_user + ':' +
                                                self.proxy_pass + '@' +
                                                parse_obj.netloc}
            else:
                self.proxy = {parse_obj.scheme: self.proxy_addr}
        else:
            self.proxy = None

        # Set HTTP request header.
        self.http_req_header = {'User-Agent': self.ua,
                                'Connection': 'keep-alive',
                                'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
                                'Accept-Encoding': 'gzip, deflate',
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                                'Upgrade-Insecure-Requests': '1',
                                'Content-Type': 'application/x-www-form-urlencoded'}

        # Setting logger.
        self.logger = getLogger(self.log_name)
        self.logger.setLevel(20)
        file_handler = FileHandler(self.log_path)
        self.logger.addHandler(file_handler)
        formatter = Formatter('%(levelname)s,%(message)s')
        file_handler.setFormatter(formatter)

    # Print metasploit's symbol.
    def print_message(self, type, message):
        if os.name == 'nt':
            if type == NOTE:
                print('[+] ' + message)
            elif type == FAIL:
                print('[-] ' + message)
            elif type == WARNING:
                print('[!] ' + message)
            elif type == NONE:
                print(message)
            else:
                print('[*] ' + message)
        else:
            if type == NOTE:
                print(PRINT_NOTE + ' ' + message)
            elif type == FAIL:
                print(PRINT_FAIL + ' ' + message)
            elif type == WARNING:
                print(PRINT_WARN + ' ' + message)
            elif type == NONE:
                print(NOTE_GREEN + message + ENDC)
            else:
                print(PRINT_OK + ' ' + message)

        return

    # Print exception messages.
    def print_exception(self, e, message):
        self.print_message(WARNING, 'type:{}'.format(type(e)))
        self.print_message(WARNING, 'args:{}'.format(e.args))
        self.print_message(WARNING, '{}'.format(e))
        self.print_message(WARNING, message)

        return

    # Write logs.
    def write_log(self, loglevel, message):
        self.logger.log(loglevel, self.get_current_date() + ' ' + message)

    # Get current date.
    def get_current_date(self, indicate_format=None):
        if indicate_format is not None:
            date_format = indicate_format
        else:
            date_format = self.report_date_format
        return datetime.now().strftime(date_format)

    # Transform date from string to object.
    def transform_date_object(self, target_date, format=None):
        if format is None:
            return datetime.strptime(target_date, self.report_date_format)
        else:
            return datetime.strptime(target_date, format)

    # Transform date from object to string.
    def transform_date_string(self, target_date):
        return target_date.strftime(self.report_date_format)

    # Delete control character.
    def delete_ctrl_char(self, origin_text):
        clean_text = ''
        for char in origin_text:
            ord_num = ord(char)
            # Allow LF,CR,SP and symbol, character and numeric.
            if (ord_num == 10 or ord_num == 13) or (32 <= ord_num <= 126):
                clean_text += chr(ord_num)

        return clean_text

    # Convert string to integer.
    def transform_string_integer(self, origin_text):
        result = ''
        for c in origin_text:
            result += str(ord(c))

        return int(result)

    # Get all player's data.
    def get_all_players(self):
        player_data = []
        try:
            cur = self.sql.select(self.sql.conn, self.sql.state_select, (1,))
            results = cur.fetchall()
            for result in results:
                player_data.append({'id': result[0],
                                    'user_id': result[4],
                                    'password': result[5],
                                    'charge': result[2],
                                    'injustice_num': result[3],
                                    'nickname': result[6],
                                    'created_at': result[7],
                                    'level': result[8],
                                    'exp': result[9],
                                    'gold': result[10],
                                    'max_hp': result[11],
                                    'max_stamina': result[12],
                                    'max_str': result[13],
                                    'need_exp': result[14],
                                    'stamina': result[15],
                                    'staminaupdated_at': result[16],
                                    'weapon_id': result[17],
                                    'armor_id': result[18]})
        except Exception as e:
            self.print_exception(e, 'Could not read the all player\'s data from Database.')
            player_data = []

        return player_data

    # Get injustice number each player.
    def get_injustice_num(self, query):
        injustice_num = 0
        try:
            cur = self.sql.select(self.sql.conn, query, (1,))
            results = cur.fetchall()
            for result in results:
                injustice_num = result[0]
        except Exception as e:
            self.print_exception(e, 'Could not read the injustice number from Database.')

        return injustice_num

    # Get player id each player.
    def get_player_id(self, user_name):
        player_id = None
        try:
            cur = self.sql.select(self.sql.conn, self.sql.state_select_id, (user_name,))
            results = cur.fetchall()
            for result in results:
                player_id = result[0]
        except Exception as e:
            self.print_exception(e, 'Could not read the injustice number from Database.')

        return player_id

    # Get the amount of charge.
    def get_player_charge(self):
        amount_charge = 0
        try:
            cur = self.sql.select(self.sql.conn, self.sql.state_select_charge, ())
            results = cur.fetchall()
            for result in results:
                amount_charge += result[0]
        except Exception as e:
            self.print_exception(e, 'Could not read the amount of charge from Database.')

        return amount_charge

    # Get the charge amount in this epoch.
    def get_player_charge_in_this_epoch(self, epoch, player_list):
        total_charge_amount_in_this_epoch = 0
        for player in player_list:
            total_charge_amount_in_this_epoch += player.charge_amount_in_this_epoch

        self.print_message(NOTE, 'Total charge amount: {}, epoch{}'.format(total_charge_amount_in_this_epoch, epoch))
        return total_charge_amount_in_this_epoch

    # Update charge amount each player.
    def update_charge_amount(self, charge, user_name):
        try:
            self.sql.update(self.sql.conn, self.sql.state_update_charge, (charge, user_name))
        except Exception as e:
            self.print_exception(e, 'Could not update the charge amount.')

        return

    # Update status each player.
    def update_user_status(self, user_name):
        try:
            self.sql.update(self.sql.conn, self.sql.state_update_inactive, (user_name,))
        except Exception as e:
            self.print_exception(e, 'Could not update the user\'s status.')

        return

    # Update injustice number each player.
    def update_injustice_num(self, injustice_num, user_name):
        try:
            self.sql.update(self.sql.conn, self.sql.state_update_injustice_num, (injustice_num, user_name))
        except Exception as e:
            self.print_exception(e, 'Could not update the injustice number.')

        return

    # Update all data of player.
    def update_all(self, player_data):
        try:
            update_items = (player_data.created_at,
                            player_data.level,
                            player_data.exp,
                            player_data.gold,
                            player_data.max_hp,
                            player_data.max_stamina,
                            player_data.max_str,
                            player_data.need_exp,
                            player_data.stamina,
                            player_data.staminaupdated_at,
                            player_data.weapon_id,
                            player_data.armor_id,
                            player_data.user_name)
            self.sql.update(self.sql.conn, self.sql.state_update_all, update_items)
        except Exception as e:
            self.print_exception(e, 'Could not update all data of player.')

    # Insert new player.
    def insert_new_user(self, user_id, password, nick_name):
        try:
            self.sql.insert(self.sql.conn, self.sql.state_insert, (1, user_id, password, nick_name))
        except Exception as e:
            self.print_exception(e, 'Could not insert new user.')

        return

    # Judge Falsification.
    def judge_falsification(self, user_status):
        try:
            # Check integrity.
            falsify_flag = False
            if user_status.max_stamina < user_status.stamina:
                self.print_message(WARNING, 'Your max stamina is smaller than current stamina.')
                falsify_flag = True
            if falsify_flag:
                self.print_message(WARNING, 'Your max_stamina is falsified!!')
                return False

            # Check gold.
            if user_status.level <= 20 and user_status.gold > 1500:
                falsify_flag = True
            elif 20 < user_status.level <= 40 and user_status.gold > 2000:
                falsify_flag = True
            elif 40 < user_status.level <= 60 and user_status.gold > 2500:
                 falsify_flag = True
            elif 60 < user_status.level <= 80 and user_status.gold > 3000:
                falsify_flag = True
            if falsify_flag:
                self.print_message(WARNING, 'Your gold is falsified!!')
                return False

            # Check max stamina.
            if user_status.level <= 20 and user_status.max_stamina > 50:
                falsify_flag = True
            elif 20 < user_status.level <= 40 and user_status.max_stamina > 100:
                falsify_flag = True
            elif 40 < user_status.level <= 60 and user_status.max_stamina > 150:
                falsify_flag = True
            elif 60 < user_status.level <= 80 and user_status.max_stamina > 200:
                falsify_flag = True
            if falsify_flag:
                self.print_message(WARNING, 'Your max stamina is falsified!!')
                return False

            # Check max hp.
            if user_status.level <= 20 and user_status.max_hp > 100:
                falsify_flag = True
            elif 20 < user_status.level <= 40 and user_status.max_hp > 150:
                falsify_flag = True
            elif 40 < user_status.level <= 60 and user_status.max_hp > 200:
                falsify_flag = True
            elif 60 < user_status.level <= 80 and user_status.max_hp > 250:
                falsify_flag = True
            if falsify_flag:
                self.print_message(WARNING, 'Your max hp is falsified!!')
                return False

            # Check max strength.
            if user_status.level <= 20 and user_status.max_str > 50:
                falsify_flag = True
            elif 20 < user_status.level <= 40 and user_status.max_str > 100:
                falsify_flag = True
            elif 40 < user_status.level <= 60 and user_status.max_str > 150:
                falsify_flag = True
            elif 60 < user_status.level <= 80 and user_status.max_str > 200:
                falsify_flag = True
            if falsify_flag:
                self.print_message(WARNING, 'Your max strength is falsified!!')
                return False

            # Check experience.
            if user_status.level <= 20 and user_status.exp > 200:
                falsify_flag = True
            elif 20 < user_status.level <= 40 and user_status.exp > 300:
                falsify_flag = True
            elif 40 < user_status.level <= 60 and user_status.exp > 800:
                falsify_flag = True
            elif 60 < user_status.level <= 80 and user_status.exp > 2500:
                falsify_flag = True
            if falsify_flag:
                self.print_message(WARNING, 'Your experience is falsified!!')
                return False
            return True
        except Exception as e:
            self.print_exception(e, 'Could not judge Falsification.')
            time.sleep(self.loop_wait_time)
            return None

    # Judge waiting time.
    def judge_waiting_time(self, player_list):
        # Compute mean.
        tmp_level = []
        for player in player_list:
            if player.level is None:
                player.level = 0
            tmp_level.append(player.level)
        if len(tmp_level) != 0:
            mean_level = mean(tmp_level)
        else:
            mean_level = 1

        # Waiting time.
        waiting_time = 0.0
        if mean_level <= 20.0:
            waiting_time = 5
        elif 20.0 < mean_level <= 40.0:
            waiting_time = 4
        elif 40.0 < mean_level <= 60.0:
            waiting_time = 3
        elif 60.0 < mean_level <= 80.0:
            waiting_time = 2
        else:
            waiting_time = 1

        return waiting_time

    # Select gatya's gold.
    def select_gatya_gold(self, level):
        # Compute gatya's price.
        if level <= 10:
            self.print_message(WARNING, 'Selected {}G.'.format(self.min_gatya_gold))
            return self.min_gatya_gold
        else:
            self.print_message(WARNING, 'Selected {}G.'.format(level * self.std_gatya_gold))
            return level * self.std_gatya_gold

    # Execute Gatya.
    def gatya_event(self):
        # Execute Gatya in Gatya rate.
        if (random.randint(1, 10)) % self.gatya_rate == 0:
            return True
        else:
            return False

    # Initialize super rare queue.
    def init_sr_queue(self):
        self.sr_queue = deque([False, False, False])

    # Get course's ID.
    def select_battle_course_id(self, user_status, course_list):
        selected_course_id = -1
        try:
            if user_status.stamina >= course_list[4]['stamina']*self.battle_stamina_rate:
                selected_course_id = course_list[4]['id']
            elif user_status.stamina >= course_list[3]['stamina']*self.battle_stamina_rate:
                selected_course_id = course_list[3]['id']
            elif user_status.stamina >= course_list[2]['stamina']*self.battle_stamina_rate:
                selected_course_id = course_list[2]['id']
            elif user_status.stamina >= course_list[1]['stamina']*self.battle_stamina_rate:
                selected_course_id = course_list[1]['id']
            elif user_status.stamina >= course_list[0]['stamina']:
                selected_course_id = course_list[0]['id']
            return selected_course_id
        except Exception as e:
            self.print_exception(e, 'Could not select course.')
            time.sleep(self.loop_wait_time)
            return False

    # Get player's wait time.
    def get_player_wait_time(self, level):
        return float((self.max_player_level - level)/10)

    # Decode parameter (name and value).
    def decode_parameter(self, params):
        parameter = {}
        for item in params.items():
            parameter[urllib.parse.unquote(item[0])] = urllib.parse.unquote(item[1])

        return parameter

    # Create http session.
    def create_http_session(self):
        # Session object for sending request.
        session = requests.session()
        if self.proxy is not None:
            session.proxies = self.proxy

        return session

    # Get ranking information.
    def get_ranking(self, session, sort='level'):
        self.http_req_header['Content-Type'] = self.api_ranking_ctype

        url = ''
        if sort == 'level':
            url = self.api_ranking_url + '?sort=1'
        elif sort == 'stamina':
            url = self.api_ranking_url + '?sort=2'
        elif sort == 'gold':
            url = self.api_ranking_url + '?sort=3'
        elif sort == 'exp':
            url = self.api_ranking_url + '?sort=4'
        elif sort == 'weapon':
            url = self.api_ranking_url + '?sort=5'
        else:
            url = self.api_ranking_url 

        status, response = self.send_request(session,
                                             self.api_ranking_method,
                                             url,
                                             self.http_req_header,
                                             None)

        if status is False:
            self.print_message(FAIL, 'Could not connect "ranking" API.')
            time.sleep(self.loop_wait_time)
            return None, None, None
        else:
            self.print_message(OK, 'Complete getting ranking information.')
            return response, None, None

    # New user registration.
    def user_registration(self, session):
        user_id = hashlib.sha256(b'userid' + self.get_current_date().encode()).hexdigest()
        password = hashlib.sha256(b'pass' + self.get_current_date().encode()).hexdigest()

        # Choice nick name from list.
        with codecs.open(os.path.join(os.getcwd(), 'nickname.txt'), mode='r', encoding='utf-8') as fin:
            nickname_list = fin.read().split('\n')
        nick_name = random.choice(nickname_list) + '_' + hashlib.md5().hexdigest()[:10]
        self.api_new_user_params['user_name'] = user_id
        self.api_new_user_params['password'] = password
        self.api_new_user_params['nick_name'] = nick_name
        self.http_req_header['Content-Type'] = self.api_new_user_ctype
        status, response = self.send_request(session,
                                             self.api_new_user_method,
                                             self.api_new_user_url,
                                             self.http_req_header,
                                             self.api_new_user_params)

        if status is False:
            self.print_message(FAIL, 'Could not connect "new_user" API.')
            time.sleep(self.loop_wait_time)
            return None, None, None
        elif type(response) != dict:
            self.print_message(WARNING, '{}'.format('"response" is not dict.'))
            time.sleep(self.loop_wait_time)
            return None, None, None
        elif 'result' not in response.keys():
            self.print_message(WARNING, '{}'.format('"result" is not included in "response".'))
            time.sleep(self.loop_wait_time)
            return None, None, None
        elif response['result'] == 'ng':
            self.print_message(WARNING, '{}'.format(response['msg']))
            time.sleep(self.loop_wait_time)
            return None, None, None
        else:
            self.print_message(OK, 'Complete registration.')
            return user_id, password, nick_name

    # User Login.
    def user_login(self, session, user_id, password):
        self.api_login_params['user_name'] = user_id
        self.api_login_params['password'] = password
        self.http_req_header['Content-Type'] = self.api_login_ctype
        status, response = self.send_request(session,
                                             self.api_login_method,
                                             self.api_login_url,
                                             self.http_req_header,
                                             self.api_login_params)
        if status is False:
            self.print_message(FAIL, 'Could not connect "login" API.')
            time.sleep(self.loop_wait_time)
            return None
        elif type(response) != dict:
            self.print_message(WARNING, '{}'.format('"response" is not dict.'))
            time.sleep(self.loop_wait_time)
            return None
        elif 'result' not in response.keys():
            self.print_message(WARNING, '{}'.format('"result" is not included in "response".'))
            time.sleep(self.loop_wait_time)
            return None
        elif response['result'] == 'ng':
            self.print_message(WARNING, '{}'.format(response['msg']))
            time.sleep(self.loop_wait_time)
            return None
        elif 'session_id' not in response.keys():
            self.print_message(WARNING, '{}'.format('"session_id" is not included in "response".'))
            time.sleep(self.loop_wait_time)
            return None
        else:
            return response['session_id']

    # Judge hacked target web site.
    def judge_hacked(self, response, regex_hacked):
        status = True
        if re.search(regex_hacked, response) is not None:
            self.print_message(WARNING, 'This site is hacked : including "{}"'.format(regex_hacked))
            status = False
        return status

    # Send score to Score Server (Elasticsearch).
    def send_score(self, team, site, score):
        status = True
        try:
            send_message = {'team': team, 'site': site, 'score': score, 'created': self.get_current_date()}
            self.es.index(index=self.elastic_index_sc, doc_type=self.elastic_doc_score, body=send_message)
            msg = 'Send score : team={}, site={}, score={}'.format(team, site, score)
            self.print_message(WARNING, msg)
            self.write_log(20, 'id={} {} [{}].'.format(self.player_id, msg, self.file_name))
        except Exception as e:
            msg = 'Could not send score : team={}, site={}, score={}'.format(team, site, score)
            self.print_exception(e, msg)
            self.write_log(20, 'id={} {} [{}].'.format(self.player_id, msg, self.file_name))
            status = False
        return status

    # Send charge to Score Server (Elasticsearch).
    def send_charge(self, team, charge):
        status = True
        try:
            send_message = {'team': team, 'charge': charge, 'created': self.get_current_date()}
            self.es.index(index=self.elastic_index_ch, doc_type=self.elastic_doc_charge, body=send_message)
            msg = 'Send charge : team={}, charge={}'.format(team, charge)
            self.print_message(WARNING, msg)
            self.write_log(20, 'id={} {} [{}].'.format(self.player_id, msg, self.file_name))
        except Exception as e:
            msg = 'Could not send charge : team={}, charge={}'.format(team, charge)
            self.print_exception(e, msg)
            self.write_log(20, 'id={} {} [{}].'.format(self.player_id, msg, self.file_name))
            status = False
        return status

    # Get file on the repository server.
    def get_repo_file(self, file_type='readme'):
        if file_type == 'readme':
            status, response = self.send_request(self.create_http_session(), 'get', self.repo_url_readme, self.http_req_header, {})
            return status, response, None
        else:
            res_hash = None
            status, response = self.send_request(self.create_http_session(), 'get', self.repo_url_csv, self.http_req_header, {})
            if status:
                res_hash = hashlib.sha256(response.encode()).hexdigest()
            return status, None, res_hash

    # Get Web site information (url, score).
    def get_web_info(self, site_type):
        target_url = ''
        score = 0
        keywords = []
        if site_type == 'corp':
            target_url = self.web_corporate_url
            score = self.web_corporate_score
            keywords = self.web_corporate_keywords
        elif site_type == 'fan':
            target_url = self.web_fansite_url
            score = self.web_fansite_score
            keywords = self.web_fansite_keywords
        elif site_type == 'saiyo':
            target_url = self.web_saiyo_url
            score = self.web_saiyo_score
            keywords = self.web_saiyo_keywords
        elif site_type == 'bbs':
            target_url = self.web_bbs_url
            score = self.web_bbs_score
            keywords = self.web_bbs_keywords
        elif site_type == 'inquiry':
            target_url = self.web_inquiry_url
            score = self.web_inquiry_score
            keywords = self.web_inquiry_keywords
        else:
            self.print_message(WARNING, '{} is not found.'.format(site_type))
            self.print_message(WARNING, 'Selected "corp" instead of {}.'.format(site_type))
            target_url = self.web_corporate_url
            score = self.web_corporate_score
            keywords = self.web_corporate_keywords

        return target_url, score, keywords

    # Send http request.
    def send_request(self, session, method, target_url, header, body_param):
        res = None

        # Decode parameter (name and value).
        if header['Content-Type'].lower() != 'application/json':
            body_param = self.decode_parameter(body_param)

        # Send request and receive response.
        try:
            res = None
            if method.lower() == 'get':
                res = session.get(target_url,
                                  data=body_param,
                                  headers=header,
                                  timeout=self.con_timeout,
                                  allow_redirects=True)
            elif method.lower() == 'post':
                if header['Content-Type'].lower() != 'application/json':
                    res = session.post(target_url,
                                       data=body_param,
                                       headers=header,
                                       timeout=self.con_timeout,
                                       allow_redirects=True)
                else:
                    res = session.post(target_url,
                                       json.dumps(body_param),
                                       headers=header,
                                       timeout=self.con_timeout,
                                       allow_redirects=True)
            else:
                self.print_message(WARNING, 'Invalid method : {}.'.format(method))
                return False, {}

            # Check response code.
            if res.status_code >= 400:
                self.print_message(FAIL, 'Occur error: status={}'.format(res.status_code))
                self.write_log(40, 'id={} Occur error: status={} [{}].'.format(res.status_code, self.player_id, self.file_name))
                return False, res.text

            # Convert from string to dictionary.
            print(res.headers['Content-Type'])
            if 'application/json' in res.headers['Content-Type'].lower():
                return True, json.loads(res.text)
            else:
                return True, res.text

        except Exception as e:
            self.print_exception(e, 'Accessing is failure : {}'.format(target_url))
            return False, {}
