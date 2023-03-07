# -*- coding:utf-8 -*-

# author: Cone
# datetime: 2023/3/5 15:33
# software: PyCharm
from typing import Dict


def nlp_config_to_schedule_config(nlp_syntax: Dict, sentence=None):
    nlp_type = nlp_syntax['type']
    definition = nlp_syntax['definition']
    config = {
        "nlp-sentence": sentence,
    }
    nlp_time = nlp_syntax['time']
    if nlp_type == 'time_point':
        config['schedule_type'] = "O"
        config['O'] = {
            "schedule_start_time": nlp_syntax['time'][0],
        }
    elif nlp_type == 'time_period':
        delta = nlp_syntax['time']['delta']
        years = delta.get('year', 0)
        months = delta.get('month', 0)
        days = delta.get('day', 0)
        hours = delta.get('hour', 0)
        minutes = delta.get('minute', 0)
        seconds = delta.get('second', 0)
        seconds = seconds + minutes * 60 + hours * 3600
        if seconds:
            config['schedule_type'] = 'S'
            config['S'] = {
                "period": seconds,
                "schedule_start_time": nlp_time['point']['time'][0],
            }
        else:
            config['schedule_type'] = "T"
            date, time = nlp_time['point']['time'][0].split()
            year, month, day = date.split('-')
            timing_config = config['T'] = {
                "time": time,
            }
            if days:
                timing_config["DAY"] = {
                    "period": days,
                }
                timing_config["type"] = "DAY"
            elif months:
                timing_config["MONTHDAY"] = {
                    "period": months,
                    "monthday": [int(day)]
                }
                timing_config["type"] = "MONTHDAY"
            elif years:
                timing_config["YEAR"] = {
                    "period": years,
                    "year": "%s-%s" % (month, day)
                }
                timing_config["type"] = "YEAR"
    return config
