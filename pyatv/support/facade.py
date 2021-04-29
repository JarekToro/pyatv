"""Facade pattern for public interface of pyatv.

This module implements a facade-like pattern by implementing the external interface
of pyatv and relaying calls to methods to the appropriate protocol instance, based on
priority via the relayer module. The purpose is to support partial implementations of
the interface by a protocol, whilst allowing another protocol to implement the rest. If
two protocols implement the same functionality, the protocol with higher "priority" is
picked. See `DEFAULT_PRIORITIES` for priority list.

NB: Typing in this file suffers much from:
https://github.com/python/mypy/issues/5374
"""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple, cast

from pyatv import conf, const, interface, net
from pyatv.const import FeatureName, FeatureState, InputAction, Protocol
from pyatv.support.relayer import Relayer

_LOGGER = logging.getLogger(__name__)

DEFAULT_PRIORITIES = [Protocol.MRP, Protocol.DMAP, Protocol.Companion, Protocol.AirPlay]

PUBLIC_INTERFACES = [
    interface.RemoteControl,
    interface.Metadata,
    interface.PushUpdater,
    interface.Stream,
    interface.Power,
    interface.Features,
    interface.Apps,
]

# TODO: These should be moved somewhere and shared with protocol implementations
SetupData = Tuple[Callable[[], Awaitable[None]], Callable[[], None], Set[FeatureName]]
SetupMethod = Callable[
    [
        asyncio.AbstractEventLoop,
        conf.AppleTV,
        Dict[Any, Relayer],
        interface.StateProducer,
        net.ClientSessionManager,
    ],
    SetupData,
]


class FacadeRemoteControl(Relayer, interface.RemoteControl):
    """Facade implementation for API used to control an Apple TV."""

    def __init__(self):
        """Initialize a new FacadeRemoteControl instance."""
        super().__init__(interface.RemoteControl, DEFAULT_PRIORITIES)

    # pylint: disable=invalid-name
    async def up(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key up."""
        return await self.relay("up")(action=action)

    async def down(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key down."""
        return await self.relay("down")(action=action)

    async def left(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key left."""
        return await self.relay("left")(action=action)

    async def right(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key right."""
        return await self.relay("right")(action=action)

    async def play(self) -> None:
        """Press key play."""
        return await self.relay("play")()

    async def play_pause(self) -> None:
        """Toggle between play and pause."""
        return await self.relay("play_pause")()

    async def pause(self) -> None:
        """Press key play."""
        return await self.relay("pause")()

    async def stop(self) -> None:
        """Press key stop."""
        return await self.relay("stop")()

    async def next(self) -> None:
        """Press key next."""
        return await self.relay("next")()

    async def previous(self) -> None:
        """Press key previous."""
        return await self.relay("previous")()

    async def select(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key select."""
        return await self.relay("select")(action=action)

    async def menu(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key menu."""
        return await self.relay("menu")(action=action)

    async def volume_up(self) -> None:
        """Press key volume up."""
        return await self.relay("volume_up")()

    async def volume_down(self) -> None:
        """Press key volume down."""
        return await self.relay("volume_down")()

    async def home(self, action: InputAction = InputAction.SingleTap) -> None:
        """Press key home."""
        return await self.relay("home")(action=action)

    async def home_hold(self) -> None:
        """Hold key home."""
        return await self.relay("home_hold")()

    async def top_menu(self) -> None:
        """Go to main menu (long press menu)."""
        return await self.relay("top_menu")()

    async def suspend(self) -> None:
        """Suspend the device."""
        return await self.relay("suspend")()

    async def wakeup(self) -> None:
        """Wake up the device."""
        return await self.relay("wakeup")()

    async def skip_forward(self) -> None:
        """Skip forward a time interval.

        Skip interval is typically 15-30s, but is decided by the app.
        """
        return await self.relay("skip_forward")()

    async def skip_backward(self) -> None:
        """Skip backwards a time interval.

        Skip interval is typically 15-30s, but is decided by the app.
        """
        return await self.relay("skip_backward")()

    async def set_position(self, pos: int) -> None:
        """Seek in the current playing media."""
        return await self.relay("set_position")(pos=pos)

    async def set_shuffle(self, shuffle_state: const.ShuffleState) -> None:
        """Change shuffle mode to on or off."""
        return await self.relay("set_shuffle")(shuffle_state=shuffle_state)

    async def set_repeat(self, repeat_state: const.RepeatState) -> None:
        """Change repeat state."""
        return await self.relay("set_repeat")(repeat_state=repeat_state)


class FacadeMetadata(Relayer, interface.Metadata):
    """Facade implementation for retrieving metadata from an Apple TV."""

    def __init__(self):
        """Initialize a new FacadeMetadata instance."""
        super().__init__(interface.Metadata, DEFAULT_PRIORITIES)

    @property
    def device_id(self) -> Optional[str]:
        """Return a unique identifier for current device."""
        return self.relay("device_id")

    async def artwork(self, width=512, height=None) -> Optional[interface.ArtworkInfo]:
        """Return artwork for what is currently playing (or None).

        The parameters "width" and "height" makes it possible to request artwork of a
        specific size. This is just a request, the device might impose restrictions and
        return artwork of a different size. Set both parameters to None to request
        default size. Set one of them and let the other one be None to keep original
        aspect ratio.
        """
        return await self.relay("artwork")(width=width, height=height)

    @property
    def artwork_id(self) -> str:
        """Return a unique identifier for current artwork."""
        return self.relay("artwork_id")

    async def playing(self) -> interface.Playing:
        """Return what is currently playing."""
        return await self.relay("playing")()

    @property
    def app(self) -> Optional[interface.App]:
        """Return information about current app playing something.

        Do note that this property returns which app is currently playing something and
        not which app is currently active. If nothing is playing, the corresponding
        feature will be unavailable.
        """
        return self.relay("app")


class FacadeFeatures(Relayer, interface.Features):
    """Facade implementation for supported feature functionality.

    This class holds a map from feature name to an instance handling that feature name.
    It is optimized for look up speed rather than memory usage.
    """

    def __init__(self) -> None:
        """Initialize a new FacadeFeatures instance."""
        super().__init__(interface.Features, DEFAULT_PRIORITIES)
        self._feature_map: Dict[FeatureName, Tuple[Protocol, interface.Features]] = {}

    def add_mapping(self, protocol: Protocol, features: Set[FeatureName]) -> None:
        """Add mapping from protocol to features handled by that protocol."""
        instance = cast(interface.Features, self.get(protocol))
        if instance:
            for feature in features:
                # Add feature to map if missing OR replace if this protocol has higher
                # priority than previous mapping
                if feature not in self._feature_map or self._has_higher_priority(
                    protocol, self._feature_map[feature][0]
                ):
                    self._feature_map[feature] = (protocol, instance)

    def get_feature(self, feature_name: FeatureName) -> interface.FeatureInfo:
        """Return current state of a feature."""
        if feature_name in self._feature_map:
            return self._feature_map[feature_name][1].get_feature(feature_name)
        return interface.FeatureInfo(FeatureState.Unsupported)

    @staticmethod
    def _has_higher_priority(first: Protocol, second: Protocol) -> bool:
        return DEFAULT_PRIORITIES.index(first) < DEFAULT_PRIORITIES.index(second)


class FacadePower(Relayer, interface.Power, interface.PowerListener):
    """Facade implementation for retrieving power state from an Apple TV.

    Listener interface: `pyatv.interfaces.PowerListener`
    """

    def __init__(self):
        """Initialize a new FacadePower instance."""
        # This is border line, maybe need another structure to support this
        Relayer.__init__(self, interface.Power, DEFAULT_PRIORITIES)
        interface.Power.__init__(self)

    def powerstate_update(
        self, old_state: const.PowerState, new_state: const.PowerState
    ):
        """Device power state was updated.

        Forward power state updates from protocol implementations to actual listener.
        """
        self.listener.powerstate_update(old_state, new_state)

    @property
    def power_state(self) -> const.PowerState:
        """Return device power state."""
        return self.relay("power_state")

    async def turn_on(self, await_new_state: bool = False) -> None:
        """Turn device on."""
        await self.relay("turn_on")(await_new_state=await_new_state)

    async def turn_off(self, await_new_state: bool = False) -> None:
        """Turn device off."""
        await self.relay("turn_off")(await_new_state=await_new_state)


class FacadeStream(Relayer, interface.Stream):  # pylint: disable=too-few-public-methods
    """Facade implementation for stream functionality."""

    def __init__(self):
        """Initialize a new FacadeStream instance."""
        super().__init__(interface.Stream, DEFAULT_PRIORITIES)

    def close(self) -> None:
        """Close connection and release allocated resources."""
        self.relay("close")()

    async def play_url(self, url: str, **kwargs) -> None:
        """Play media from an URL on the device."""
        await self.relay("play_url")(url, **kwargs)


class FacadeApps(Relayer, interface.Apps):
    """Facade implementation for app handling."""

    def __init__(self):
        """Initialize a new FacadeApps instance."""
        super().__init__(interface.Apps, DEFAULT_PRIORITIES)

    async def app_list(self) -> List[interface.App]:
        """Fetch a list of apps that can be launched."""
        return await self.relay("app_list")()

    async def launch_app(self, bundle_id: str) -> None:
        """Launch an app based on bundle ID."""
        await self.relay("launch_app")(bundle_id)


class FacadeAppleTV(interface.AppleTV):
    """Facade implementation of the external interface."""

    def __init__(self, config: conf.AppleTV, session_manager: net.ClientSessionManager):
        """Initialize a new FacadeAppleTV instance."""
        super().__init__()
        self._config = config
        self._session_manager = session_manager
        self._protocol_handlers: Dict[Protocol, SetupData] = {}
        self._features = FacadeFeatures()
        self.interfaces = {
            interface.Features: self._features,
            interface.RemoteControl: FacadeRemoteControl(),
            interface.Metadata: FacadeMetadata(),
            interface.Power: FacadePower(),
            interface.PushUpdater: Relayer(
                interface.PushUpdater, DEFAULT_PRIORITIES  # type: ignore
            ),
            interface.Stream: FacadeStream(),
            interface.Apps: FacadeApps(),
        }

    def add_protocol(self, protocol: Protocol, setup_data: SetupData):
        """Add a new protocol to the relay."""
        self._protocol_handlers[protocol] = setup_data
        self._features.add_mapping(protocol, setup_data[2])

    async def connect(self) -> None:
        """Initiate connection to device."""
        # TODO: Parallelize with asyncio.gather? Needs to handle cancling
        # of ongoing tasks in case of error.
        for protocol_connect, _, _ in self._protocol_handlers.values():
            await protocol_connect()

    def close(self) -> None:
        """Close connection and release allocated resources."""
        asyncio.ensure_future(self._session_manager.close())
        for _, protocol_close, _ in self._protocol_handlers.values():
            protocol_close()

    @property
    def device_info(self) -> interface.DeviceInfo:
        """Return API for device information."""
        return self._config.device_info

    @property
    def service(self) -> interface.BaseService:
        """Return main service used to connect to the Apple TV."""
        for protocol in DEFAULT_PRIORITIES:
            service = self._config.get_service(protocol)
            if service:
                return service

        raise RuntimeError("no service (bug)")

    @property
    def remote_control(self) -> interface.RemoteControl:
        """Return API for controlling the Apple TV."""
        return cast(interface.RemoteControl, self.interfaces[interface.RemoteControl])

    @property
    def metadata(self) -> interface.Metadata:
        """Return API for retrieving metadata from the Apple TV."""
        return cast(interface.Metadata, self.interfaces[interface.Metadata])

    @property
    def push_updater(self) -> interface.PushUpdater:
        """Return API for handling push update from the Apple TV."""
        return self.interfaces[interface.PushUpdater].main_instance  # type: ignore

    @property
    def stream(self) -> interface.Stream:
        """Return API for streaming media."""
        return cast(interface.Stream, self.interfaces[interface.Stream])

    @property
    def power(self) -> interface.Power:
        """Return API for power management."""
        return cast(interface.Power, self.interfaces[interface.Power])

    @property
    def features(self) -> interface.Features:
        """Return features interface."""
        return cast(interface.Features, self.interfaces[interface.Features])

    @property
    def apps(self) -> interface.Apps:
        """Return apps interface."""
        return cast(interface.Apps, self.interfaces[interface.Apps])