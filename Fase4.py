"""Sistema Software FJ: gestión en memoria de clientes, servicios y reservas.

Curso Programación 213023 - Fase 4. Python 3.10+; sin dependencias externas.
Los archivos se usan exclusivamente para registrar eventos y errores.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum
import logging
from pathlib import Path
from typing import overload

# SEGMENTO 1. Configuración del registro de eventos y errores.
# Se escribe en un archivo log; si no es posible, se utiliza la consola.
LOG = logging.getLogger('software_fj')
LOG.setLevel(logging.INFO)
LOG.propagate = False
if not LOG.handlers:
    try:
        handler = logging.FileHandler(Path(__file__).with_name('software_fj.log'), encoding='utf-8')
    except OSError:
        handler = logging.StreamHandler()  # La aplicación sigue operativa si falla el disco.
    handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    LOG.addHandler(handler)


# SEGMENTO 2. Excepciones propias para identificar y controlar fallos del negocio.
class ErrorSistema(Exception):
    """Error de negocio recuperable que no debe cerrar la aplicación."""


class DatoInvalido(ErrorSistema):
    """Un campo no satisface sus restricciones."""


class Duplicado(ErrorSistema):
    """Ya existe un elemento con el identificador indicado."""


class NoEncontrado(ErrorSistema):
    """No existe el elemento solicitado."""


class ServicioNoDisponible(ErrorSistema):
    """El servicio no está disponible o carece de capacidad."""


class OperacionNoPermitida(ErrorSistema):
    """La transición de estado solicitada es inválida."""


# SEGMENTO 3. Funciones de validación reutilizables para textos, números y porcentajes.
def texto_obligatorio(valor: object, campo: str) -> str:
    """Valida que un texto no esté vacío ni compuesto solo de espacios."""
    if not isinstance(valor, str) or not valor.strip():
        raise DatoInvalido(f'{campo} debe ser un texto no vacío.')
    return valor.strip()


def positivo(valor: object, campo: str) -> Decimal:
    """Convierte un número finito y estrictamente positivo a Decimal."""
    if isinstance(valor, bool):
        raise DatoInvalido(f'{campo} debe ser numérico.')
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DatoInvalido(f'{campo} debe ser numérico.') from exc
    if not numero.is_finite() or numero <= 0:
        raise DatoInvalido(f'{campo} debe ser mayor que cero y finito.')
    return numero


def porcentaje(valor: object, campo: str) -> Decimal:
    """Acepta tasas entre cero y uno, incluidos ambos extremos."""
    if isinstance(valor, bool):
        raise DatoInvalido(f'{campo} debe ser numérico.')
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DatoInvalido(f'{campo} debe ser numérico.') from exc
    if not numero.is_finite() or not 0 <= numero <= 1:
        raise DatoInvalido(f'{campo} debe estar entre 0 y 1.')
    return numero


# SEGMENTO 4. Clase abstracta base: define la identidad y descripción de cada entidad.
class Entidad(ABC):
    """Abstracción común para los objetos identificables del sistema."""

    def __init__(self, identificador: str):
        self.__identificador = texto_obligatorio(identificador, 'Identificador')

    @property
    def identificador(self) -> str:
        """Expone el identificador sin permitir modificarlo."""
        return self.__identificador

    @abstractmethod
    def describir(self) -> str:
        """Devuelve una descripción legible de la entidad."""


# SEGMENTO 5. Clientes: encapsula datos y valida nombre y correo electrónico.
class Cliente(Entidad):
    """Cliente con datos encapsulados y validados."""

    def __init__(self, identificador: str, nombre: str, correo: str):
        super().__init__(identificador)
        self.__nombre = texto_obligatorio(nombre, 'Nombre')
        self.__correo = self._validar_correo(correo)

    @staticmethod
    def _validar_correo(correo: str) -> str:
        correo = texto_obligatorio(correo, 'Correo')
        if correo.count('@') != 1 or '.' not in correo.split('@')[1] or ' ' in correo:
            raise DatoInvalido('Correo electrónico inválido.')
        return correo

    @property
    def nombre(self) -> str:
        return self.__nombre

    @property
    def correo(self) -> str:
        return self.__correo

    def actualizar_correo(self, nuevo: str) -> None:
        """Permite cambiar el correo únicamente tras validarlo."""
        self.__correo = self._validar_correo(nuevo)

    def describir(self) -> str:
        return f'Cliente {self.identificador}: {self.nombre}'


# SEGMENTO 6. Servicio abstracto: tarifas, cupos, disponibilidad y costo total.
# La sobrecarga se declara con @overload y se implementa con parámetros opcionales.
class Servicio(Entidad, ABC):
    """Contrato abstracto para servicios especializados y sus tarifas."""

    def __init__(self, identificador: str, nombre: str, tarifa: object, capacidad: int = 1):
        super().__init__(identificador)
        self.__nombre = texto_obligatorio(nombre, 'Nombre del servicio')
        self.__tarifa = positivo(tarifa, 'Tarifa')
        if type(capacidad) is not int or capacidad < 1:
            raise DatoInvalido('Capacidad debe ser un entero positivo.')
        self.__capacidad = capacidad
        self.__ocupacion = 0
        self.__disponible = True

    @property
    def nombre(self) -> str:
        return self.__nombre

    @property
    def tarifa(self) -> Decimal:
        return self.__tarifa

    @property
    def disponible(self) -> bool:
        return self.__disponible and self.__ocupacion < self.__capacidad

    def cambiar_disponibilidad(self, disponible: bool) -> None:
        if type(disponible) is not bool:
            raise DatoInvalido('Disponibilidad debe ser booleana.')
        self.__disponible = disponible

    def ocupar(self) -> None:
        if not self.disponible:
            raise ServicioNoDisponible(f'{self.nombre} no tiene disponibilidad.')
        self.__ocupacion += 1

    def liberar(self) -> None:
        if self.__ocupacion <= 0:
            raise OperacionNoPermitida('No hay cupos ocupados para liberar.')
        self.__ocupacion -= 1

    @abstractmethod
    def validar_parametros(self, duracion: object) -> Decimal:
        """Valida y devuelve la duración expresada en horas."""

    @abstractmethod
    def calcular_costo(self, duracion: object) -> Decimal:
        """Calcula el costo base según el servicio concreto."""

    @abstractmethod
    def describir(self) -> str:
        """Describe el tipo de servicio y su tarifa."""

    @overload
    def calcular_total(self, duracion: object) -> Decimal: ...

    @overload
    def calcular_total(self, duracion: object, impuesto: object, descuento: object = 0) -> Decimal: ...

    def calcular_total(self, duracion: object, impuesto: object = 0, descuento: object = 0) -> Decimal:
        """Sobrecarga por argumentos opcionales: aplica descuento e impuesto.

        Fórmula: costo_base * (1 - descuento) * (1 + impuesto).
        Tasas expresadas como fracciones: 0.19 equivale al 19 %.
        """
        base = self.calcular_costo(duracion)
        tasa = porcentaje(impuesto, 'Impuesto')
        rebaja = porcentaje(descuento, 'Descuento')
        return (base * (1 - rebaja) * (1 + tasa)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# SEGMENTO 7. Sala: valida horas y calcula el precio de su reserva.
class Sala(Servicio):
    """Alquiler de sala con tarifa por hora y mínimo de una hora."""

    def validar_parametros(self, duracion: object) -> Decimal:
        horas = positivo(duracion, 'Duración de sala')
        if horas < 1 or horas > 12:
            raise DatoInvalido('La sala requiere entre 1 y 12 horas.')
        return horas

    def calcular_costo(self, duracion: object) -> Decimal:
        return self.tarifa * self.validar_parametros(duracion)

    def describir(self) -> str:
        return f'Sala: {self.nombre} (${self.tarifa}/hora)'


# SEGMENTO 8. Equipo: valida duración y aplica su regla de facturación.
class Equipo(Servicio):
    """Alquiler de equipo con descuento base por duración larga."""

    def validar_parametros(self, duracion: object) -> Decimal:
        horas = positivo(duracion, 'Duración de equipo')
        if horas > 72:
            raise DatoInvalido('El equipo admite máximo 72 horas.')
        return horas

    def calcular_costo(self, duracion: object) -> Decimal:
        horas = self.validar_parametros(duracion)
        factor = Decimal('0.90') if horas >= 24 else Decimal('1')
        return self.tarifa * horas * factor

    def describir(self) -> str:
        return f'Equipo: {self.nombre} (${self.tarifa}/hora; 10 % desde 24 h)'


# SEGMENTO 9. Asesoría: valida horas y aplica su cálculo especializado.
class Asesoria(Servicio):
    """Asesoría con recargo del 20 % a partir de la tercera hora."""

    def validar_parametros(self, duracion: object) -> Decimal:
        horas = positivo(duracion, 'Duración de asesoría')
        if horas > 8:
            raise DatoInvalido('La asesoría admite máximo 8 horas.')
        return horas

    def calcular_costo(self, duracion: object) -> Decimal:
        horas = self.validar_parametros(duracion)
        normal = min(horas, Decimal('2'))
        extra = max(Decimal('0'), horas - 2)
        return self.tarifa * (normal + extra * Decimal('1.20'))

    def describir(self) -> str:
        return f'Asesoría: {self.nombre} (${self.tarifa}/hora; recargo después de 2 h)'


# SEGMENTO 10. Estados permitidos en el ciclo de vida de una reserva.
class EstadoReserva(Enum):
    PENDIENTE = 'PENDIENTE'
    CONFIRMADA = 'CONFIRMADA'
    CANCELADA = 'CANCELADA'


# SEGMENTO 11. Reservas: relaciona cliente y servicio; confirma, cancela y procesa.
# Se controla la disponibilidad y se recupera la operación ante errores.
class Reserva(Entidad):
    """Vincula cliente y servicio; controla transiciones y ocupación."""

    def __init__(self, identificador: str, cliente: Cliente, servicio: Servicio, duracion: object):
        super().__init__(identificador)
        if not isinstance(cliente, Cliente) or not isinstance(servicio, Servicio):
            raise DatoInvalido('La reserva requiere cliente y servicio válidos.')
        self.__duracion = servicio.validar_parametros(duracion)
        self.__cliente = cliente
        self.__servicio = servicio
        self.__estado = EstadoReserva.PENDIENTE
        self.__total: Decimal | None = None

    @property
    def estado(self) -> EstadoReserva:
        return self.__estado

    @property
    def total(self) -> Decimal | None:
        return self.__total

    @property
    def servicio(self) -> Servicio:
        return self.__servicio

    def confirmar(self, impuesto: object = 0, descuento: object = 0) -> Decimal:
        """Calcula antes de ocupar; evita reservar cupos ante cálculos fallidos."""
        if self.__estado != EstadoReserva.PENDIENTE:
            raise OperacionNoPermitida('Solo se confirman reservas pendientes.')
        total = self.__servicio.calcular_total(self.__duracion, impuesto, descuento)
        self.__servicio.ocupar()
        self.__total = total
        self.__estado = EstadoReserva.CONFIRMADA
        LOG.info('Reserva %s confirmada: total=%s', self.identificador, total)
        return total

    def cancelar(self) -> None:
        """Cancela una reserva y libera capacidad si estaba confirmada."""
        if self.__estado == EstadoReserva.CANCELADA:
            raise OperacionNoPermitida('La reserva ya fue cancelada.')
        if self.__estado == EstadoReserva.CONFIRMADA:
            self.__servicio.liberar()
        self.__estado = EstadoReserva.CANCELADA
        LOG.info('Reserva %s cancelada', self.identificador)

    def procesar(self, impuesto: object = 0, descuento: object = 0) -> bool:
        """try/except/else/finally: captura fallos sin detener la aplicación."""
        try:
            self.confirmar(impuesto, descuento)
        except ErrorSistema as exc:
            LOG.error('Error procesando reserva %s: %s', self.identificador, exc)
            return False
        else:
            LOG.info('Procesamiento exitoso: %s', self.identificador)
            return True
        finally:
            LOG.info('Finalizó intento de procesamiento de %s', self.identificador)

    def describir(self) -> str:
        return (f'Reserva {self.identificador}: {self.__cliente.nombre} / '
                f'{self.__servicio.nombre} / {self.__duracion} h / {self.estado.value}')


# SEGMENTO 12. Gestor central: conserva listas en memoria y evita duplicados.
class GestorSoftwareFJ:
    """Almacena objetos únicamente en listas, sin base de datos."""

    def __init__(self):
        self.__clientes: list[Cliente] = []
        self.__servicios: list[Servicio] = []
        self.__reservas: list[Reserva] = []

    @property
    def clientes(self) -> tuple[Cliente, ...]:
        return tuple(self.__clientes)

    @property
    def servicios(self) -> tuple[Servicio, ...]:
        return tuple(self.__servicios)

    @property
    def reservas(self) -> tuple[Reserva, ...]:
        return tuple(self.__reservas)

    @staticmethod
    def _buscar(elementos: list[Entidad], identificador: str) -> Entidad:
        for elemento in elementos:
            if elemento.identificador == identificador:
                return elemento
        raise NoEncontrado(f'No existe el identificador {identificador}.')

    def registrar_cliente(self, identificador: str, nombre: str, correo: str) -> Cliente:
        if any(c.identificador == identificador for c in self.__clientes):
            raise Duplicado(f'Cliente {identificador} duplicado.')
        cliente = Cliente(identificador, nombre, correo)
        self.__clientes.append(cliente)
        LOG.info('Cliente registrado: %s', identificador)
        return cliente

    def registrar_servicio(self, servicio: Servicio) -> Servicio:
        if not isinstance(servicio, Servicio):
            raise DatoInvalido('Se requiere un servicio válido.')
        if any(s.identificador == servicio.identificador for s in self.__servicios):
            raise Duplicado(f'Servicio {servicio.identificador} duplicado.')
        self.__servicios.append(servicio)
        LOG.info('Servicio registrado: %s', servicio.identificador)
        return servicio

    def crear_reserva(self, identificador: str, id_cliente: str, id_servicio: str, duracion: object) -> Reserva:
        if any(r.identificador == identificador for r in self.__reservas):
            raise Duplicado(f'Reserva {identificador} duplicada.')
        try:
            cliente = self._buscar(self.__clientes, id_cliente)
            servicio = self._buscar(self.__servicios, id_servicio)
        except NoEncontrado as exc:
            raise NoEncontrado(f'No fue posible crear la reserva {identificador}: {exc}') from exc
        reserva = Reserva(identificador, cliente, servicio, duracion)
        self.__reservas.append(reserva)
        LOG.info('Reserva creada: %s', identificador)
        return reserva

    def obtener_reserva(self, identificador: str) -> Reserva:
        return self._buscar(self.__reservas, identificador)


# SEGMENTO 13. Simulación: ejecuta 22 operaciones válidas e inválidas.
# try/except/else/finally permite registrar fallos y continuar con el siguiente caso.
def simulacion() -> None:
    """Ejecuta 20 casos independientes; registra fallos y continúa."""
    gestor = GestorSoftwareFJ()
    casos = [
        ('Cliente válido', lambda: gestor.registrar_cliente('C01', 'Ana Pérez', 'ana@correo.com')),
        ('Cliente inválido: correo', lambda: gestor.registrar_cliente('C02', 'Luis', 'correo-malo')),
        ('Cliente válido 2', lambda: gestor.registrar_cliente('C03', 'Sara López', 'sara@correo.com')),
        ('Cliente duplicado', lambda: gestor.registrar_cliente('C01', 'Otro', 'otro@correo.com')),
        ('Sala válida', lambda: gestor.registrar_servicio(Sala('S01', 'Sala Norte', 50000, 1))),
        ('Equipo válido', lambda: gestor.registrar_servicio(Equipo('S02', 'Portátil', 12000, 2))),
        ('Asesoría válida', lambda: gestor.registrar_servicio(Asesoria('S03', 'Python', 80000, 1))),
        ('Servicio inválido: tarifa', lambda: gestor.registrar_servicio(Sala('S04', 'Sala mala', -5))),
        ('Servicio duplicado', lambda: gestor.registrar_servicio(Equipo('S02', 'Otro', 10000))),
        ('Reserva válida sala', lambda: gestor.crear_reserva('R01', 'C01', 'S01', 2)),
        ('Confirmar sala', lambda: gestor.obtener_reserva('R01').confirmar(Decimal('0.19'))),
        ('Reserva sin cupo', lambda: gestor.crear_reserva('R02', 'C03', 'S01', 1).confirmar()),
        ('Reserva duración inválida', lambda: gestor.crear_reserva('R03', 'C01', 'S02', -2)),
        ('Reserva cliente inexistente', lambda: gestor.crear_reserva('R04', 'C99', 'S02', 2)),
        ('Reserva válida equipo', lambda: gestor.crear_reserva('R05', 'C03', 'S02', 24)),
        ('Procesar equipo', lambda: gestor.obtener_reserva('R05').procesar(Decimal('0.19'), Decimal('0.05'))),
        ('Reserva válida asesoría', lambda: gestor.crear_reserva('R06', 'C01', 'S03', 3)),
        ('Procesar asesoría con impuesto inválido', lambda: gestor.obtener_reserva('R06').procesar(2)),
        ('Procesar asesoría correctamente', lambda: gestor.obtener_reserva('R06').procesar()),
        ('Cancelar sala y liberar cupo', lambda: gestor.obtener_reserva('R01').cancelar()),
        ('Confirmación repetida', lambda: gestor.obtener_reserva('R05').confirmar()),
        ('Reserva posterior a liberación', lambda: gestor.crear_reserva('R07', 'C03', 'S01', 1).confirmar()),
    ]
    exitos, errores = 0, 0
    for numero, (nombre, accion) in enumerate(casos, 1):
        try:
            resultado = accion()
        except ErrorSistema as exc:
            errores += 1
            LOG.error('Caso %02d (%s): %s', numero, nombre, exc)
            print(f'{numero:02d}. ERROR CONTROLADO | {nombre}: {exc}')
        except Exception:
            errores += 1
            LOG.exception('Caso %02d (%s): fallo inesperado', numero, nombre)
            print(f'{numero:02d}. ERROR INESPERADO | {nombre}; consultar log')
        else:
            exitos += 1
            detalle = resultado.describir() if isinstance(resultado, Entidad) else str(resultado)
            print(f'{numero:02d}. OK | {nombre}: {detalle}')
        finally:
            LOG.info('Caso %02d finalizado', numero)
    print(f'\nTotal: {len(casos)} operaciones | {exitos} sin excepción | {errores} errores controlados.')
    print(f'Clientes: {len(gestor.clientes)} | Servicios: {len(gestor.servicios)} | Reservas: {len(gestor.reservas)}')
    print('Log: software_fj.log (junto al archivo main.py, si el disco permite escribir).')


# SEGMENTO 14. Punto de entrada: inicia la simulación al ejecutar el archivo.
if __name__ == '__main__':
    simulacion()
