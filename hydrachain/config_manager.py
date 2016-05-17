import json


DEFAULT_CONFIG_FILE = 'datadir/hdc_config.json'


class ConfigManager:
    def __init__(self):
        self.config_file = DEFAULT_CONFIG_FILE

    def add(self, key, value):
        previous_config = self.read()
        previous_config[key] = value
        with open(self.config_file, 'w') as f:
            json.dump(previous_config, f)

    def read(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                return config
        except IOError as err:
            return {}

    def read_value(self, key):
        config = self.read()
        if key in config:
            return config[key]
        raise KeyError("{} missing from config".format(key))