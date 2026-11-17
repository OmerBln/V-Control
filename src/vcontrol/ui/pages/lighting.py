from vcontrol.ui.rgb_panel import RGBPanel


class LightingPage(RGBPanel):
    """Aydınlatma sekmesi."""

    @property
    def panel(self) -> RGBPanel:
        return self
