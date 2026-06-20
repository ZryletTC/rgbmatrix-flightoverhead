# pylint: disable=invalid-name
"""
Module to use in place of rgbmatrix if that is not found.
Displays what would be on the LED matrix in a separate window using PIL.
"""

# from tkinter import *
# from tkinter import ttk
from dataclasses import dataclass
import PIL
import matplotlib as mpl
import matplotlib.pyplot as plt


mpl.rcParams["toolbar"] = "None"


# pylint: disable=too-many-instance-attributes
@dataclass
class RGBMatrixOptions:
    """Essentially a struct of options for the RGBMatrix."""

    hardware_mapping: str

    rows: int
    cols: int
    chain_length: int
    parallel: int
    pwm_bits: int
    pwm_lsb_nanoseconds: int
    brightness: int
    scan_mode: int
    row_address_type: int
    multiplexing: int
    pwm_dither_bits: int
    limit_refresh_rate_hz: int

    disable_hardware_pulsing: bool
    show_refresh_rate: bool
    inverse_colors: bool

    led_rgb_sequence: str
    pixel_mapper_config: str
    panel_type: str

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            self.__setattr__(key, val)


# class RGBMatrix:
#     """Simulated RGBMatrix which shows matrix content as an image."""

#     def __init__(self, options: RGBMatrixOptions):
#         self.options = options

#         self.root = Tk()
#         self.root.title("Simulated RGBMatrix")
#         # self.frame = ttk.Frame(self.root)
#         # self.frame.grid(column=0, row=0, sticky=(N, W, E, S))

#         self.canvas = Canvas(self.root)

#         self.root.mainloop()

class RGBMatrix:
    """Simulated RGBMatrix which shows matrix content as an image."""

    def __init__(self, options: RGBMatrixOptions):
        self.options = options

        plt.ion()
        self.fig, self.ax = plt.subplots(num="Simulated RGBMatrix")
        # self.fig.canvas.set_window_title("Simulated RGBMatrix")
        self.Clear()
        self.fig.show()

    def SetImage(self, image: PIL.Image):
        """Change the image shown on the matrix."""
        self.ax.imshow(image)

    def Clear(self):
        """Set the matrix to show a black screen."""
        width = self.options.cols
        height = self.options.rows
        self.SetImage(PIL.Image.new("RGB", (width, height), "#000"))
