import requests
import json
import re
from datetime import datetime, timedelta
import iso8601
from operator import itemgetter
import os
from dotenv import load_dotenv
import subprocess

load_dotenv()


src_registry_url = os.getenv("SRC_REGISTRY_URL")
src_registry_user = os.getenv("SRC_REGISTRY_USER")
src_registry_pass = os.getenv("SRC_REGISTRY_PASS")

dest_registry_url = os.getenv("DEST_REGISTRY_URL")
dest_registry_user = os.getenv("DEST_REGISTRY_USER")
dest_registry_pass = os.getenv("DEST_REGISTRY_PASS")


def write_repositories_with_tags_to_file():

    basic = requests.auth.HTTPBasicAuth(src_registry_user, src_registry_pass)

    r = requests.get("https://"+src_registry_url+"/v2/_catalog", auth=basic)

    repositories = {}

    json_object = r.json()

    repo_counter = 0

    for i in json_object['repositories']:
        tags = []
        print(i)
        r = requests.get("https://"+src_registry_url+"/v2/" + i + "/tags/list", auth=basic)
        r_json = r.json()

        for t in r_json['tags']:
            tags.append({'name': t, 'date': ''})

        repositories.update({i: tags})
        repo_counter = repo_counter + 1
        # if repo_counter >= 2:
        #     break

    patern = r'((?:(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}(?:\.\d+)?))(Z|[\+-]\d{2}:\d{2})?)'
    for repo, tags in repositories.items():
        print(repo)
        for t in tags:
            r = requests.get("https://"+src_registry_url+"/v2/" + repo + "/manifests/" + t['name'], auth=basic)
            r_json = r.json()
            dt_last = datetime.now() - timedelta(days=30*365)
            dt_last = dt_last.replace(tzinfo=None)

            for hist in r_json['history']:
                result_date = re.search(patern, hist['v1Compatibility'])
                if result_date:
                    dt = iso8601.parse_date(result_date.group())
                    dt = dt.replace(tzinfo=None)
                    if dt > dt_last:
                        dt_last = dt

            t['date'] = dt_last

    for repo, tags in repositories.items():
        tags = sorted(tags, key=itemgetter('date'), reverse=True)
        for t in tags:
            tag_date = t['date']
            tag_str_date = tag_date.strftime('%Y-%m-%d %X')
            tag_int_date = int(tag_date.strftime('%Y%m%d%H%M%S'))
            t['date'] = tag_str_date
            t['intdate'] = tag_int_date
    for repo, tags in repositories.items():
        tags = sorted(tags, key=itemgetter('intdate'), reverse=True)

    with open('result.json', 'w') as fp:
        json.dump(repositories, fp, indent=1)

def print_repositories_from_file():
    with open('result.json') as fp:
        repositories = json.load(fp)
    repo_list = {}

    for repo, tags in repositories.items():
        repo_list.update({repo: []})
        tags = sorted(tags, key=itemgetter('intdate'), reverse=True)
        print("------")
        print("repo: " + repo)
        tags_counter = 0
        l = []
        for t in tags:
            tags_counter = tags_counter + 1
            if tags_counter > 10:
                break
            l.append(t['name'])
            # l.append(repo + ":" + t['name'])
            print("tag name: " + t['name'])
            print(t['date'])
        repo_list[repo] = l
        print("------")
    with open('ten_last_tags.json', 'w') as fp:
        json.dump(repo_list, fp, indent=1)
    return repo_list

def copy_images_from_to(repo_list):
    for repo, tags in repo_list.items():
        for tag in tags:
            command = "skopeo copy --src-creds {src_registry_user}:{src_registry_pass} --dest-creds {dest_registry_user}:{dest_registry_pass} docker://{src_registry_url}/{repo}:{tag} docker://{dest_registry_url}/{repo}:{tag}".format(
                repo=repo,
                tag=tag,
                src_registry_url=src_registry_url,
                dest_registry_url=dest_registry_url,
                src_registry_user=src_registry_user,
                src_registry_pass=src_registry_pass,
                dest_registry_user=dest_registry_user,
                dest_registry_pass=dest_registry_pass
                )
            if "domain_notify/alertmanager" in command:
                print("start copy repo " + repo + " tag: " + tag)
                subprocess.run(command, shell=True)

# write_repositories_with_tags_to_file()
repo_list = print_repositories_from_file()

copy_images_from_to(repo_list)

print("end")
