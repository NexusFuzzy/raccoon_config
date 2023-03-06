import requests
import random
import json

TRIAGE_API_KEY = ""
SUBMIT_TO_TRIAGE = True


class TriageResult:
    botnet_id = ""
    servers = []

    def __init__(self, botnet_id, servers):
        self.botnet_id = botnet_id
        self.servers = servers


def check_triage(max_items):
    headers = {"Authorization": "Bearer " + TRIAGE_API_KEY}

    result = requests.get("https://tria.ge/api/v0/search?query=family:raccoon&limit=" + max_items,
                          headers=headers).json()


    triage_results = []
    for s in result['data']:
        try:
            print("Checking task " + s['id'] + " (" + s['filename'] + ")")
            overview = requests.get("https://tria.ge/api/v0/samples/" + s['id'] + "/overview.json",
                                    headers=headers).json()
            try:
                for extracted in overview['extracted']:
                    triage_results.append(TriageResult(servers=extracted['config']['c2'],
                                                       botnet_id=extracted['config']['botnet']))
                    print("Successfully extracted C&C information - Added to the queue!")
            except Exception as ex:
                print("Couldn't extract necessary information from Tria.ge result: " + str(ex))
                print(s)
                pass
        except:
            print("Couldn't parse result from Tria.ge ")
            print(json.dumps(s))


    print("Returning " + str(len(triage_results)) + " results from Tria.ge")
    return triage_results


def submit_to_triage(url):
    print("Submitting " + url + " to Tria.ge")
    endpoint = "https://tria.ge/api/v0/samples"
    data = {"url": url, "kind": "fetch"}
    headers = {"Authorization": "Bearer " + TRIAGE_API_KEY}
    reply = requests.post(endpoint, data=data, headers=headers).json()

    if reply.get("error"):
        print("Tria.ge reported an error: " + reply["message"])
    elif reply.get("id"):
        print("Submitted to Tria.ge with ID " + reply.get("id"))
    else:
        print("Unknown reply from Tria.ge: " + reply)


def parse_config(c2_config):
    config_json = {}

    # Just a very rudimentary parser for now
    lines = c2_config.split("\n")
    for line in lines:
        if line.startswith("ldr_"):
            line_parts = line.split("|")
            url = line_parts[0][line_parts[0].index("http"):]
            if SUBMIT_TO_TRIAGE:
                submit_to_triage(url)

    print(c2_config)

    # Since ldr_1 happens to be in the config more than once we need to treat them differently
    # since we can't have a key with the same name in the JSON twice
    ldr_counter = 0
    for line in lines:
        try:
            k = line[:line.index(":")]
            if k == "ldr_1":
                k = "ldr_1_" + str(ldr_counter)
                ldr_counter += 1

            v = line[line.index(":"):]
            config_json[k] = v
        except:
            print("Line '" + line + " couldn't be added to config JSON")
    return config_json


def random_string(length):
    return ''.join(random.choice('0123456789abcdef') for i in range(length)).lower()


def create_machine_id():
    return random_string(8) + "-" + random_string(4) + "-" + random_string(4) + "12"


def knock(c2, config_id):
    try:
        # configId is the rc4 key extracted by Tria.ge
        # Value of User-Agent does NOT to be considered yet
        headers = {"User-Agent": "901785252113",
                   "Accept": "*/*",
                   "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                   "Cache-Control": "no-cache",
                   "Connection": "Keep-Alive"}
        reply = requests.post(c2, data="machineId=" + create_machine_id() + "|Admin&configId=" + config_id,
                              timeout=15, headers=headers)
        if reply.status_code == 200:
            if "Installed applications:" in reply.text:
                print("C2 returned valid config")
                return reply.text
        else:
            return ""

    except Exception as ex:
        print("We got an error while checking the server: " + str(ex))
        return ""


if __name__ == '__main__':
    triage_results = check_triage("50")
    for result in triage_results:
        config_extracted = False
        for server in result.servers:
            if not config_extracted:
                print("Checking server " + server)
                config = knock(server, result.botnet_id)
                if config != "":
                    print("Successfully extracted config from C2!")
                    config_extracted = True
                    config_json = parse_config(config)

                    print(json.dumps(config_json, indent=4))

