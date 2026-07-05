class ZteC300Commands:
    @staticmethod
    def find_onu_by_sn(sn: str) -> str:
        return f"show gpon onu by sn {sn}\n"

    @staticmethod
    def bulk_diagnostics(port: str) -> str:
        return (
            f"show gpon onu detail-info {port}\n"
            f"show pon power attenuation {port}\n"
            f"show gpon remote-onu interface eth {port}\n"
            f"show interface {port}\n"
            f"show ip-service user status {port}\n"
            f"show ip dhcp snooping dynamic port pon {port} sport 1\n"
        )