"""
TimeSeriesTransformer 모델 아키텍처
노트북에서 사용한 모델과 동일한 구조를 정의합니다.
"""

import torch
import torch.nn as nn


class TimeSeriesTransformer(nn.Module):
    """
    Time Series Transformer for Cyanobacteria Prediction
    
    입력:
    - Time series features (cyano + wq vars) at t, t-1, ..., t-6: (batch, seq_len=7, num_features)
    - Temporal context (WoY): (batch,)
    - Spatial context (location): (batch,)
    
    출력:
    - Cyanobacteria variables at t+1: (batch, num_cyano_vars)
    """
    
    def __init__(
        self,
        num_features,            # Total number of features (cyano + wq)
        num_cyano_vars,          # Number of cyanobacteria variables to predict
        num_temporal_categories, # Number of temporal categories (WoY)
        num_spatial_categories,  # Number of spatial categories (locations)
        d_model=128,             # Model dimension
        nhead=8,                 # Number of attention heads
        num_layers=4,            # Number of transformer encoder layers
        dim_feedforward=512,     # Feedforward dimension
        dropout=0.1,             # Dropout rate
        max_seq_len=7            # Sequence length (t to t-6)
    ):
        super(TimeSeriesTransformer, self).__init__()
        
        self.d_model = d_model
        self.max_seq_len = max_seq_len
        
        # Input projection: project time series features to d_model
        self.input_projection = nn.Linear(num_features, d_model)
        
        # Temporal embedding: WoY -> d_model
        self.temporal_embedding = nn.Embedding(num_temporal_categories, d_model)
        
        # Spatial embedding: location -> d_model
        self.spatial_embedding = nn.Embedding(num_spatial_categories, d_model)
        
        # Positional encoding for time series
        self.pos_encoding = nn.Parameter(torch.randn(max_seq_len, d_model))
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Context fusion: combine temporal and spatial embeddings
        self.context_fusion = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout)
        )
        
        # Output head: predict cyanobacteria at t+1
        self.output_head = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, dim_feedforward),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, dim_feedforward // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward // 2, num_cyano_vars)
        )
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.02)
    
    def forward(self, x_time_series, temporal_context, spatial_context):
        """
        Forward pass
        
        Args:
            x_time_series: (batch, seq_len=7, num_features) - time series features
            temporal_context: (batch,) - WoY values (0-53)
            spatial_context: (batch,) - spatial location indices
        
        Returns:
            predictions: (batch, num_cyano_vars) - predicted cyanobacteria at t+1
        """
        seq_len = x_time_series.size(1)
        
        # Project time series features to d_model
        x = self.input_projection(x_time_series)  # (batch, seq_len, d_model)
        
        # Add positional encoding
        x = x + self.pos_encoding[:seq_len, :].unsqueeze(0)  # (batch, seq_len, d_model)
        
        # Transformer encoding
        transformer_out = self.transformer(x)  # (batch, seq_len, d_model)
        
        # Pooling: mean over sequence length
        pooled = transformer_out.mean(dim=1)  # (batch, d_model)
        
        # Temporal and spatial embeddings
        temporal_emb = self.temporal_embedding(temporal_context)  # (batch, d_model)
        spatial_emb = self.spatial_embedding(spatial_context)  # (batch, d_model)
        
        # Fuse temporal and spatial context
        context_combined = torch.cat([temporal_emb, spatial_emb], dim=1)  # (batch, 2*d_model)
        context_fused = self.context_fusion(context_combined)  # (batch, d_model)
        
        # Combine pooled features with context
        final_features = pooled + context_fused  # (batch, d_model)
        
        # Predict cyanobacteria
        predictions = self.output_head(final_features)  # (batch, num_cyano_vars)
        
        return predictions

