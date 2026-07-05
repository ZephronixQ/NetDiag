class ZteC600Commands:
    @staticmethod
    def find_onu_by_sn(sn: str) -> str:
        return f"show gpon onu by sn {sn}\n"

    @staticmethod
    def port_identification(vport_name: str) -> str:
        return f"show port-identification port {vport_name} service-port 1\n"

    @staticmethod
    def bulk_diagnostics(port: str, vport_name: str) -> str:
        return (
            f"show gpon onu detail-info {port}\n"
            f"show pon power attenuation {port}\n"
            f"show gpon remote-onu interface eth {port}\n"
            f"show interface {port}\n"
            f"show ip dhcp snooping dynamic port {vport_name}\n"
        )