"""
Modelos y esquemas de validación para la estación meteorológica.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field, field_validator


class WeatherReading(BaseModel):
    """
    Representa una lectura física validada de la estación Sainlogic.
    """
    temperatura: float = Field(ge=-20.0, le=50.0, description="Temperatura ambiente en °C")
    humedad: int = Field(ge=0, le=100, description="Humedad relativa en %")
    viento_medio: float = Field(ge=0.0, le=150.0, description="Velocidad media del viento en m/s")
    rafaga: float = Field(ge=0.0, le=200.0, description="Ráfaga máxima de viento en m/s")
    direccion: int = Field(ge=0, le=360, description="Dirección del viento en grados (0-360)")
    lluvia_raw: float = Field(ge=0.0, le=2000.0, description="Lluvia acumulada medida por el sensor en mm")

    @field_validator('viento_medio')
    @classmethod
    def check_viento(cls, v: float, info) -> float:
        # Validación de coherencia física: la ráfaga no puede ser menor que el viento medio
        if 'rafaga' in info.data and v > info.data['rafaga']:
            return info.data['rafaga']
        return v

    @classmethod
    def from_raw_bytes(cls, msg: bytes, rain_offset: float = 642.2) -> "WeatherReading":
        """
        Convierte el paquete binario de 16+ bytes enviado por el ESP32
        en una lectura estructurada y validada.
        """
        if len(msg) < 16 or msg[0] != 255 or msg[1] != 212:
            raise ValueError("Cabecera de mensaje inválida (esperado 0xFF 0xD4)")

        data = msg[2:]
        flags_wind = data[1] & 0x0F

        return cls(
            temperatura=round((((((data[7] & 0x0F) << 8) | data[8]) - 400) / 10.0 - 32) * 5/9, 1),
            humedad=int(data[9]),
            viento_medio=round((data[2] | ((flags_wind & 0x01) << 8)) * 0.1, 1),
            rafaga=round((data[3] | ((flags_wind & 0x02) << 8)) * 0.1, 1),
            direccion=int(data[4] | ((flags_wind & 0x04) << 8)),
            lluvia_raw=round((((data[5] & 0x0F) << 8) | data[6]) * 0.1 + rain_offset, 1)
        )

    def to_db_dict(self, scale_factor: float = 10.0) -> Dict[str, Any]:
        """
        Convierte las magnitudes reales a enteros escalados para persistencia SQLite.
        """
        return {
            "temperatura": int(round(self.temperatura * scale_factor)),
            "humedad": self.humedad,
            "viento_medio": int(round(self.viento_medio * scale_factor)),
            "rafaga": int(round(self.rafaga * scale_factor)),
            "direccion": int(round(self.direccion * scale_factor)),
            "lluvia": int(round(self.lluvia_raw * scale_factor))
        }
