#!/usr/bin/env python3
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

def compare_robot_state(fast_behavior: bool, cyclone_behavior: bool) -> int:
    if fast_behavior and cyclone_behavior:
        return 1
    elif fast_behavior and not cyclone_behavior:
        return 2
    elif not fast_behavior and cyclone_behavior:
        return 3
    else:
        return 4

def listener_parser(file_path: str):
    events = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) < 4:
                parts += [''] * (4 - len(parts))
            time_str, event_type, entity, msg_or_count = parts[:4]

            # 1) Parse timestamp -> TODO List after Confirming Log Format
                if time_str.endswith('Z'):
                    ts = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                else:
                    ts = datetime.fromisoformat(time_str)
            except ValueError:
                ts = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)

            # 2) Determine if the fourth column is numeric -> TODO List after Confirming Log Format
            detail = {}
            if msg_or_count.isdigit():
                detail['count'] = int(msg_or_count)
            else:
                detail['message'] = msg_or_count

            event = {
                "timestamp": ts,
                "event_type": event_type,
                "entity": entity,
                "detail": detail
            }
            events.append(event)
    return events

def compare_listener(events_a: list, events_b: list, topic:str):

    mapping = {
        "data available":                 "DATA_AVAILABLE",
        "subscription matched":           "SUBSCRIPTION_MATCHED",
        "requested_deadline_missed":      "REQUESTED_DEADLINE_MISSED",
        "liveliness_lost":                "LIVELINESS_LOST",
        "offered_deadline_missed":        "OFFERED_DEADLINE_MISSED",
        "requested_incompatible_qos":     "REQUESTED_INCOMPATIBLE_QOS",
        "sample_lost":                    "SAMPLE_LOST",
        "offered_incompatible_qos":       "OFFERED_INCOMPATIBLE_QOS",
        "liveliness_changed":             "LIVELINESS_CHANGED",
    }
    # Log Abstracting for Classification
    def abstract(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for ev in events:
            if ev["entity"] != topic:
                continue
            abs_type = mapping.get(ev["raw_event"])
            if not abs_type:
                continue
            parts = ev["detail"].split(';')
            seq = None
            msg = ""
            for p in parts:
                if p.startswith("seq:"):
                    try:
                        seq = int(p.split(":",1)[1])
                    except:
                        pass
                elif abs_type == "DATA_AVAILABLE" and p.startswith("msg:"):
                    msg = p.split(":",1)[1]
            out.append({
                "timestamp": ev["timestamp"],
                "type":      abs_type,
                "seq":       seq,
                "msg":       msg
            })
        return sorted(out, key=lambda e: e["timestamp"])

    cmd_fast    = abstract(events_a)
    cmd_cyclone = abstract(events_b)

    # analyze events call or counts
    def analyze(events: List[Dict[str, Any]]) -> Dict[str, Any]:
        pre_matched = 0
        pre_others  = set()
        data_msgs   = []
        post_matched = 0
        post_others  = set()

        data_times = [e["timestamp"] for e in events if e["type"] == "DATA_AVAILABLE"]
        if data_times:
            cutoff_first = min(data_times)
            cutoff_last  = max(data_times)
        else:
            cutoff_first = datetime.max.replace(tzinfo=timezone.utc)
            cutoff_last  = datetime.min.replace(tzinfo=timezone.utc)

        for ev in events:
            t  = ev["timestamp"]
            et = ev["type"]
            if et == "DATA_AVAILABLE":
                data_msgs.append(ev["msg"])
            elif t < cutoff_first:
                if et == "SUBSCRIPTION_MATCHED":
                    pre_matched += 1
                else:
                    pre_others.add(et)
            elif t > cutoff_last:
                if et == "SUBSCRIPTION_MATCHED":
                    post_matched += 1
                else:
                    post_others.add(et)

        return {
            "pre_matched_cnt":  pre_matched,
            "pre_others":       sorted(pre_others),
            "data_cnt":         len(data_msgs),
            "data_msgs":        data_msgs,
            "post_matched_cnt": post_matched,
            "post_others":      sorted(post_others)
        }

    m_fast    = analyze(cmd_fast)
    m_cyclone = analyze(cmd_cyclone)

    # compare
    for key in ("pre_matched_cnt","pre_others","data_cnt","data_msgs","post_matched_cnt","post_others"):
        if m_fast[key] != m_cyclone[key]:
            return False
    return True

def main(behavior_a, behavior_b):
    result = compare_robot_state(behavior_a, behavior_b)
    
    # result == 1 (Robotic status is normal in all DDS environments)
    if result == 1:
        return 1

    # result == 2 (Fast True, Cyclone False) OR result == 3 (Fast False, Cyclone True)
    if result in (2, 3):

        # 2) DDS Log File Path
        fast_log = "/tmp/fast_listener.log"
        cyclone_log = "/tmp/cyclone_listener.log"

        # 3) DDS Log Parsing
        events_fast = listener_parser(fast_log)
        events_cyclone = listener_parser(cyclone_log)

        # 4) DDS Listener Compare
        same = compare_listener(events_fast, events_cyclone)
        if same:
            return 1    #Considering Point
        else:
            return result

    else:   #Robotic status is unnormal in all DDS environments
        return 4

    '''
    #When performing DDS Listener differential analysis in all robot motion situations

    # 1) DDS Log File Path
    fast_log = "/tmp/fast_listener.log"
    cyclone_log = "/tmp/cyclone_listener.log"

    # 2) DDS Log Parsing
    events_fast = listener_parser(fast_log)
    events_cyclone = listener_parser(cyclone_log)

    # 3) DDS Listener Compare
    same = compare_listener(events_fast, events_cyclone)
    result = compare_robot_state(behavior_a, behavior_b)

    if same and result == 1:
        return 1
    elif same and result == 4:
        return 4
    elif !same and result in (2,3):
        return result
    else:
        return 5
    '''

if __name__ == "__main__":
    main()
