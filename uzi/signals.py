from blinker import NamedSignal


on_container_create = NamedSignal(f"{__package__}.on_container_create")
on_container_init = NamedSignal(f"{__package__}.on_container_init")
on_provider_registered = NamedSignal(f"{__package__}.on_provider_registered")
on_injector_init = NamedSignal(f"{__package__}.on_injector_init")
on_scope_init = NamedSignal(f"{__package__}.on_scope_init")
