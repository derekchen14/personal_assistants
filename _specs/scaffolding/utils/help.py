import os
import numpy as np
import torch
import random
import json

if torch.cuda.is_available():
    dtype = 'cuda'
elif torch.backends.mps.is_available():
    dtype = 'mps'
else:
    dtype = 'cpu'
device = torch.device(dtype)

def set_seed(args):
  random.seed(args.seed)
  np.random.seed(args.seed)
  torch.manual_seed(args.seed)
  if args.n_gpu > 0:
    torch.cuda.manual_seed_all(args.seed)

def setup_gpus(args):
  n_gpu = 0  # set the default to 0
  if torch.cuda.is_available():
    n_gpu = torch.cuda.device_count()
  args.n_gpu = n_gpu
  if n_gpu > 0:   # this is not an 'else' statement and cannot be combined
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
  return args

def check_directories(args):
  task_path = os.path.join("modeling", args.output_dir, args.model, args.task)
  save_path = os.path.join(task_path, args.method)

  if not os.path.exists(task_path):
    os.makedirs(task_path)
    print(f"Created {task_path} for {args.task} results")
  if not os.path.exists(save_path):
    os.makedirs(save_path)
    print(f"Created {save_path} directory")

  # cache_path = os.path.join(args.input_dir, 'cache', args.dataset)
  # if args.domain:
  #   cache_path = os.path.join(cache_path, args.domain)
  if args.debug:
    args.log_interval /= 10
  return args, save_path

def extract_flow_type(flow_name):
  # Flow names are given in 'Parent(child)' format
  parent_type, child_type = flow_name.split('(')
  child_type = child_type.rstrip(')')
  return parent_type, child_type

dact_parts = ['chat', 'query', 'measure', 'plot', 'retrieve', 'insert', 'update', 'delete',
                 'user', 'agent', 'table', 'row', 'column', 'multiple', 'confirm', 'deny']
dialogue_acts = {
  '001':'query', '01A':'pivot', '002':'measure', '02D':'segment', '014':'describe', '14C':'exist', '248':'inform', '268':'define',
  '003':'plot',  '023':'trend', '038':'explain', '23D':'report',  '38A':'save', '136':'design', '13A':'style',
  '006':'update', '36D':'validate', '36F':'format', '0BD':'pattern', '068':'persist', '06B':'impute', '06E':'datatype', '06F':'undo',  '7BD':'dedupe',
  '005':'insert', '007':'delete', '056':'transpose', '057':'move', '5CD':'split', '05A':'jointab', '05B':'append', '05C':'merge',  '456':'call', '58A':'materialize',
  '46B':'blank', '46C':'concern',  '46D':'connect', '46E':'typo', '46F':'problem', '468':'resolve', '146':'insight',
  '089':'think', '39B':'peek', '129':'compute', '149':'search',  '19A':'stage', '489':'consider',  '9DF':'uncertain',
  '000': 'chat', '004': 'faq', '008': 'user', '009': 'agent', '00A': 'table', '00B': 'row', '00C': 'column', '00D': 'multiple', '00E': 'positive', '00F': 'negative'
}

def dax2dact(dax, form='string'):
  dact_list = []
  for digit in dax:
    # Convert each hexadecimal digit to index position
    dact_index = int(digit, 16)
    if dact_index > 0:   # zero is reserved for ambiguity
      dact_list.append( dact_parts[dact_index] )
  if len(dact_list) == 0:
    dact_list.append(dact_parts[0])  # default to 'chat' (ie. dialog act is ambiguous)

  if form == 'string':
    return ' + '.join(dact_list)
  return dact_list

def dax2flow(dax):
  return dialogue_acts.get(dax, 'none')

def flow2dax(flow_name):
  for dax, name in dialogue_acts.items():
    if name == flow_name:
      return dax
  return 'none'

def dact2dax(dact):
  # converts a dact list into a dax string
  dact_list = dact.split(' + ') if isinstance(dact, str) else dact
  positions = [i for i, dialog_act in enumerate(dact_parts) if dialog_act in dact_list]
  dax_string = ''.join(format(pos, 'X') for pos in positions)
  return dax_string.zfill(3)

def dax2intent(dax, form='hex'):
  # convert to dax if input is actually in dact form
  if form == 'string' or len(dax) > 3:
    dax = dact2dax(dax)

  # handle some special cases first
  if dax in ['089', '39B', '129', '149', '19A', '489', '9DF']:
    return 'Internal'
  elif '46' in dax:
    return 'Detect'
  elif dax.startswith('36') or dax.endswith('BD'):
    return 'Clean'

  # default to converse
  dax = dax.lstrip('0')
  intent = 'Converse'

  if dax:
    first_digit = int(dax[0], 16)  # Convert to int using base 16
    if '5' in dax or '7' in dax:
      intent = 'Transform'
    elif '3' in dax:
      intent = 'Visualize'
    elif first_digit in [1, 2]:
      intent = 'Analyze'
    elif '6' in dax:
      intent = 'Clean'
  return intent