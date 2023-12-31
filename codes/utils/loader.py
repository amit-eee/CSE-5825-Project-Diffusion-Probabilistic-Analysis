import torch
import random
import numpy as np
from models.denoising_model import denoising_model
from method_series.gaussian_ddpm_losses import gaussian_ddpm_losses
import torch.nn.functional as F


def load_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    return seed


def load_device():
    if torch.cuda.is_available():
        device = list(range(torch.cuda.device_count()))
    else:
        device = 'cpu'
    return device

import torch
import numpy as np

def apply_sparsity(model, sparsity_level, sparsity_type='random'):
    if sparsity_type not in ['random', 'row']:
        raise ValueError("sparsity_type must be 'random' or 'row'")

    with torch.no_grad():
        for param in model.parameters():
            if len(param.size()) > 1:  # Only apply to weight matrices, not biases
                if sparsity_type == 'random':
                    # Apply random sparsity
                    mask = torch.FloatTensor(param.size()).uniform_() > sparsity_level
                    param.mul_(mask)
                elif sparsity_type == 'row':
                    # Apply row sparsity
                    num_rows = param.size(0)
                    num_rows_to_zero = int(sparsity_level * num_rows)
                    rows_to_zero = np.random.choice(num_rows, num_rows_to_zero, replace=False)
                    param[rows_to_zero] = 0.0
    return model


def load_model(params):
    params_ = params.copy()
    model = denoising_model(**params_)
    model = apply_sparsity(model, 0.5, sparsity_type='random')
    return model


def load_model_optimizer(params, config_train, device):
    model = load_model(params)
    if isinstance(device, list):
        if len(device) > 1:
            model = torch.nn.DataParallel(model, device_ids=device)
        model = model.to(f'cuda:{device[0]}')
    optimizer = torch.optim.Adam(model.parameters(), lr=config_train.lr, 
                                    weight_decay=config_train.weight_decay)
    scheduler = None
    if config_train.lr_schedule:
        scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=config_train.lr_decay)
    return model, optimizer, scheduler


def load_data(config):
    from utils.data_loader import dataloader
    return dataloader(config)


def load_batch(batch, device, data):
    device_id = f'cuda:{device[0]}' if isinstance(device, list) else device
    x_b = batch.x.to(device_id).view(-1, batch.x.shape[-1]).float()
    adj_b = batch.edge_index.to(device_id).view(2, -1)
    y_b = batch.y.to(device_id)
    batch_b = batch.batch.to(device_id)
    maximum = y_b.max()

    if data == 'cora':
        y_b = F.one_hot(y_b.view(-1), 7).float()
        return x_b, adj_b, y_b, batch_b
    elif data == 'pubmed':
        y_b = F.one_hot(y_b.view(-1), 3).float()
        return x_b, adj_b, y_b, batch_b
    elif data == 'citeseer':
        y_b = F.one_hot(y_b.view(-1), 6).float()
        return x_b, adj_b, y_b, batch_b
    elif data.startswith('ppi'):
        y_b = y_b.view(-1, 121).float()
        return x_b, adj_b, y_b, torch.tensor([0])
    elif data == 'dblp':
        y_b = F.one_hot(y_b.view(-1), 3).float()
        return x_b, adj_b, y_b, torch.tensor([0])


def load_loss_fn(config, device):
    if config.diffusion.method == 'Gaussian':
        return gaussian_ddpm_losses(config.diffusion.step, device = device, time_batch = config.train.time_batch, s = config.diffusion.s, unweighted_MSE = config.train.unweighted_MSE)


def load_model_params(config):
    config_m = config.model
    nlabel = config.data.nlabel
    params_ = {'model':config_m.model, 'num_linears': config_m.num_linears, 'nhid': config_m.nhid, 
                'nfeat': config.data.nfeat, 'cat_mode':config_m.cat_mode, 'skip':config_m.skip,
                'nlabel': nlabel,'num_layers':config_m.num_layers, 'types': config.diffusion.method}
    return params_
