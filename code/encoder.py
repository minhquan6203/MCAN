import torch
from torch import nn

from positionwise_feed_forward import PositionWiseFeedForward
from attention import MultiHeadAttention
from pos_embedding import SinusoidPositionalEmbedding

class EncoderLayer(nn.Module):
    def __init__(self, config):
        super(EncoderLayer, self).__init__()
        self.mhatt = MultiHeadAttention(config)
        self.pwff = PositionWiseFeedForward(config)

    def forward(self, queries, keys, values, attention_mask, **kwargs):
        att = self.mhatt(queries=queries, keys=keys, values=values, attention_mask=attention_mask, **kwargs)
        ff = self.pwff(att)

        return ff


class CoAttentionEncoder(nn.Module):
    '''
        This module is designed inspired from ViLBERT (https://arxiv.org/pdf/1908.02265.pdf).
    '''
    def __init__(self, config):
        super(CoAttentionEncoder, self).__init__()

        self.pos_embedding = SinusoidPositionalEmbedding(config.D_MODEL)
        self.vision_layer_norm = nn.LayerNorm(config.D_MODEL)
        self.language_layer_norm = nn.LayerNorm(config.D_MODEL)

        self.d_model = config.D_MODEL

        # cross-attention layers
        self.vision_language_attn_layers = nn.ModuleList([EncoderLayer(config.VISION_LANGUAGE_ATTENTION) for _ in range(config.LAYERS)])
        self.language_vision_attn_layers = nn.ModuleList([EncoderLayer(config.LANGUAGE_VISION_ATTENTION) for _ in range(config.LAYERS)])

        # self-attention layers
        self.vision_self_attn_layers = nn.ModuleList([EncoderLayer(config.VISION_SELF_ATTENTION) for _ in range(config.LAYERS)])
        self.language_self_attn_layers = nn.ModuleList([EncoderLayer(config.LANGUAGE_SELF_ATTENTION) for _ in range(config.LAYERS)])

    def forward(self, vision_features: torch.Tensor, vision_padding_mask: torch.Tensor, 
                language_features: torch.Tensor, language_padding_mask: torch.Tensor):
        vision_features = self.vision_layer_norm(vision_features) + self.pos_embedding(vision_features)
        language_features = self.language_layer_norm(language_features) + self.pos_embedding(language_features)
        for layers in zip(self.vision_language_attn_layers, 
                            self.language_vision_attn_layers, 
                            self.vision_self_attn_layers, 
                            self.language_self_attn_layers):
            vision_language_attn_layer, language_vision_attn_layer, vision_self_attn_layer, language_self_attn_layer = layers
            # performing cross-attention
            vision_features = vision_language_attn_layer(
                queries=vision_features,
                keys=language_features,
                values=language_features,
                attention_mask=language_padding_mask
            )
            language_features = language_vision_attn_layer(
                queries=language_features,
                keys=vision_features,
                values=vision_features,
                attention_mask=vision_padding_mask
            )
            # performing self-attention
            vision_features = vision_self_attn_layer(
                queries=vision_features,
                keys=vision_features,
                values=vision_features,
                attention_mask=vision_padding_mask
            )
            language_features = language_self_attn_layer(
                queries=language_features,
                keys=language_features,
                values=language_features,
                attention_mask=language_padding_mask
            )

        return vision_features, language_features

