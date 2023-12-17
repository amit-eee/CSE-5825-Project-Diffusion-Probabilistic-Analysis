import yaml
from easydict import EasyDict as edict


def get_config(config, seed):
    config_dir = f'./confignew/{config}.yaml'
    config = edict(yaml.load(open(config_dir, 'r'), Loader=yaml.FullLoader))
    config.seed = seed

    return config