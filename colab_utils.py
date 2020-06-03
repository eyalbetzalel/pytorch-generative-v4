"""Utilities to make life easier when working with Google Colaboratory.

Warning: This module must be imported from Colab, otherwise it will crash.
"""

import collections
import os

import PIL
from google.colab import files
import matplotlib
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import torch
from torchvision import transforms

# Always use html5 for animations so they can be rendered inline on Colab.
matplotlib.rcParams['animation.html'] = 'html5'

_IMAGE_UNLOADER = transforms.Compose([
  transforms.Lambda(lambda x: x.cpu().clone().squeeze(0)),
  transforms.ToPILImage()
])


def get_device():
  """Returns the appropriate device depending on what's available."""
  return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def upload_files():
  """Creates a widget to upload files from your local machine to Colab.

  The files are saved in '/tmp/<file_name>'.
  """
  uploaded = files.upload()
  for name, data in uploaded.items():
    with open(f'/tmp/{name}', 'wb') as f:
      f.write(data)


def load_image(path, size=None, remove_alpha_channel=True):
  """Loads an image from the given path as a torch.Tensor.

  Args:
    path: The path to the image to load.
    size: Either None, an integer, or a pair of integers. If not None, the 
      image is resized to the given size before being returned.
    remove_alpha_channel: If True, removes the alpha channel from the image.
  Returns:
    The loaded image as a torch.Tensor.
  """ 
  transform = []
  if size is not None:
    size = size if isinstance(size, collections.Sequence) else (size, size)
    assert len(size) == 2, "'size' must either be a scalar or contain 2 items"
    transform.append(transforms.Resize(size))
  transform.append(transforms.ToTensor())
  image_loader = transforms.Compose(transform)

  image = PIL.Image.open(path)
  image = image_loader(image)
  if remove_alpha_channel:
      image = image[:3, :, :]
  image = image.to(torch.float)

  return image
  

def imshow(tensor, title=None, figsize=None):
  """Renders the given tensor as an image using Matplotlib.

  Args:
    tensor: The tensor to render as an image.
    title: The title for the rendered image. Passed to Matplotlib.
    figsize: The size (in inches) for the image. Passed to Matplotlib.
  """
  image = _IMAGE_UNLOADER(tensor)

  plt.figure(figsize=figsize)
  plt.title(title)
  plt.axis('off')
  plt.imshow(image)


def animate(frames, figsize=None, fps=24):
  """Renders the given frames together into an animation.
  
  Args:
    frames: Either a list, iterator, or generator of images in torch.Tensor 
      format.
    figsize: The display size for the animation; passed to Matplotlib.
    fps: The number of frames to render per second (i.e. frames per second).
  Returns:
    The Matplotlib animation object.
  """
  fig = plt.figure(figsize=figsize)
  fig.subplots_adjust(left=0, bottom=0, right=1, top=1)
  plt.axis('off')

  # We pass a fake 2x2 image to 'imshow' since it does not allow None or empty
  # lists to be passed in. The fake image data is then updated by animate_fn.
  image = plt.imshow([[0, 0], [0, 0]])
  def animate_fn(frame):
    frame = _IMAGE_UNLOADER(frame)
    image.set_data(frame)
    return image,

  anim = animation.FuncAnimation(
      fig, 
      animate_fn, 
      frames=frames, 
      interval=1000 / fps,
      blit=True,
      # Caching frames causes OOMs in Colab when there are a lot of frames or 
      # the size of individual frames is large.
      cache_frame_data=False)
  plt.close(anim._fig)
  return anim


def _train_one_epoch(model, loss_fn, optimizer, train_loader, device):
    model.train()
    train_loss, n_examples = 0., 0
    for x, y in train_loader:
        batch_size = x.shape[0]
        n_examples += batch_size

        optimizer.zero_grad()
        x = x.to(device)
        preds = model(x)
        loss = loss_fn(x, y, preds)
        loss.backward()
        optimizer.step()

        train_loss += loss.item() * batch_size
    return train_loss / n_examples


def _eval_one_epoch(model, loss_fn, eval_loader, device):
    model.eval()
    eval_loss, n_examples = 0., 0
    with torch.no_grad():
        for x, y in eval_loader:
            batch_size = x.shape[0]
            n_examples += batch_size

            x = x.to(device)
            preds = model(x)
            loss = loss_fn(x, y, preds)
            eval_loss += loss.item() * batch_size
    return eval_loss / n_examples


def train_andor_eval(model,
                     loss_fn,
                     optimizer=None,
                     n_epochs=None,
                     train_loader=None,
                     eval_loader=None,
                     device=torch.device('cpu')):
    """Trains and/or evaluates the model on the datasets.
    
    Evaluations are run after every epoch.

    Args:
        model: The model to train and/or evaluate.
        loss_fn: A fn(inputs, targets, predictions)->loss.
        optimizer: The optimizer to use when training. Must not be None if
            train_loader is not None.
        n_epochs: The number of epochs to train for. Must not be None if 
            train_loader is not None. Eval always runs for one full epoch.
        train_loader: A DataLoader for the training set.
        eval_loader: A DataLoader for the evaluation set.
        device: The device to place the model and data batches on.
    Returns:
        (train_losses, eval_losses) per epoch.
    """
    model = model.to(device)

    train_losses = []
    eval_losses = []
    assert train_loader is not None or eval_loader is not None, \
           'train_loader and eval_loader cannot both be None'
    if train_loader is not None:
        assert optimizer is not None, 'optimizer must be provided for training'
        assert n_epochs >= 1, 'n_epochs must be >= 0 for training'

        for epoch in range(1, n_epochs + 1):
            train_loss = _train_one_epoch(model, loss_fn, optimizer, 
                                          train_loader, device)
            eval_loss = _eval_one_epoch(model, loss_fn, eval_loader, device)
            print(f'[{epoch}]: train_loss={train_loss} eval_loss={eval_loss}')
            train_losses.append(train_loss)
            eval_losses.append(eval_loss)
    else:
        eval_losses.append(_eval_one_epoch)
    return train_losses, eval_losses
