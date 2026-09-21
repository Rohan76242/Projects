import torch
from torch import nn


class WakeWordModel(nn.Module):

    def __init__(self):
        super().__init__()

        self.features = nn.Sequential(

            nn.Conv1d(
                1,
                16,
                kernel_size=80,
                stride=16
            ),

            nn.ReLU(),

            nn.MaxPool1d(4),

            nn.Conv1d(
                16,
                32,
                kernel_size=9,
                stride=2
            ),

            nn.ReLU(),

            nn.MaxPool1d(4),

            nn.Conv1d(
                32,
                64,
                kernel_size=5,
                stride=2
            ),

            nn.ReLU(),

            nn.AdaptiveAvgPool1d(1)
        )

        self.classifier = nn.Sequential(

            nn.Flatten(),

            nn.Linear(64, 32),

            nn.ReLU(),

            nn.Dropout(0.3),

            nn.Linear(32, 2)
        )

    def forward(self, x):

        x = self.features(x)

        return self.classifier(x)