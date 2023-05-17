import requests
import random
import json
import argparse
import validators
import os

TRIAGE_API_KEY = ""
SUBMIT_TO_TRIAGE = False


class TriageResult:
    botnet_id = ""
    servers = []

    def __init__(self, botnet_id, servers):
        self.botnet_id = botnet_id
        self.servers = servers


def check_triage(max_items):
    headers = {"Authorization": "Bearer " + TRIAGE_API_KEY}

    result = requests.get("https://tria.ge/api/v0/search?query=family:raccoon&limit=" + str(max_items),
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
            pass
    return config_json


def random_string(length):
    return ''.join(random.choice('0123456789abcdef') for i in range(length)).lower()


def create_machine_id():
    return random_string(8) + "-" + random_string(4) + "-" + random_string(4) + "12"


def knock(c2, config_id):
    try:
        # configId is the rc4 key extracted by Tria.ge
        # Value of User-Agent does NOT to be considered yet
        headers = {"User-Agent": "AYAYAYAY1338",
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
            print("We received an answer we can't parse: " + reply.text)
            return ""

    except Exception as ex:
        print("We got an error while checking the server: " + str(ex))
        return ""


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')
    required.add_argument('--target', help="Either choose 'triage' as target to get the latest raccoon reports from Tria.ge sandbox or enter your raccoon C&C server in the format 'http://123.123.123.123/'", required=True)
    optional.add_argument('--sample_count', help="Specify the number of reports to get from Tria.ge sandbox. Default is 50", type=int)
    optional.add_argument('--config_id', help="If you choose a custom URL as target, you will also need to specify the RC4 key")
    optional.add_argument('--output', help="Save generated config JSON to specific folder additionally to showing them")
    args = parser.parse_args()

    if args.target == "triage":
        num_samples = 50
        if args.sample_count:
            num_samples = args.sample_count

        triage_results = check_triage(num_samples)
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
                        if args.output:
                            if not os.path.exists(args.output):
                                os.makedirs(args.output)
                            out_file = open(os.path.join(args.output, "config_" + server.replace("http://", "").replace("\\","").replace("/","") + ".json"), "w")
                            json.dump(config_json, out_file, indent=4)

    elif args.target != "triage":
        if validators.url(args.target):
            if args.config_id is not None:
                config = knock(args.target, args.config_id)
                if config != "":
                    print("Successfully extracted config from C2!")
                    config_extracted = True
                    config_json = parse_config(config)
                    print(json.dumps(config_json, indent=4))
                    if args.output:
                        if not os.path.exists(args.output):
                            os.makedirs(args.output)
                        out_file = open(os.path.join(args.output, "config_" + server.replace("http://", "").replace("\\","").replace("/","") + ".json"), "w")
                        json.dump(config_json, out_file, indent=4)
            else:
                print("No config_id / RC4 key specified - aborting.")
        else:
            print("Specified target couldn't be recognized as valid URL - aborting.")
            exit()
