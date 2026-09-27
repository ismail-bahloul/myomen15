// teeopen.c -- open a TEE session to an AMD-TEE Trusted Application via /dev/tee0.
//
// On this machine the amdtee driver loads the TA as firmware:
//   TEE_IOC_OPEN_SESSION -> amdtee_open_session -> request_firmware("amdtee/<uuid>.bin")
//     -> copy_ta_binary -> TEE_CMD_LOAD_TA to the PSP -> the PSP VERIFIES the
//     signature before running it.
// So the return value of OPEN_SESSION is the PSP's verdict on the blob:
//   ret == 0        the PSP accepted and loaded the TA (signature OK, and the
//                   TA's own CreateSessionEntryPoint ran)
//   ret != 0        the PSP refused it (bad signature, bad header, ...)
//
// Usage: teeopen [device] [uuid-hex-16-bytes]
//   default device /dev/tee0, default uuid 773bd96f-b83f-4d52-b12dc529b13d8543
//   (the AMD PMF TA, i.e. /lib/firmware/amdtee/773bd96f-...bin.zst).
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/tee.h>

static int parse_uuid(const char *s, unsigned char *out)
{
    // accept "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" or 32 hex chars
    int n = 0;
    for (const char *p = s; *p; p++) {
        if (*p == '-' || *p == ':') continue;
        int hi = -1, lo = -1;
        if (*p >= '0' && *p <= '9') hi = *p - '0';
        else if (*p >= 'a' && *p <= 'f') hi = *p - 'a' + 10;
        else if (*p >= 'A' && *p <= 'F') hi = *p - 'A' + 10;
        if (hi < 0) return -1;
        p++;
        if (!*p) return -1;
        if (*p >= '0' && *p <= '9') lo = *p - '0';
        else if (*p >= 'a' && *p <= 'f') lo = *p - 'a' + 10;
        else if (*p >= 'A' && *p <= 'F') lo = *p - 'A' + 10;
        if (lo < 0) return -1;
        if (n >= 16) return -1;
        out[n++] = (hi << 4) | lo;
    }
    return n == 16 ? 0 : -1;
}

int main(int argc, char **argv)
{
    const char *dev = (argc > 1) ? argv[1] : "/dev/tee0";
    // /dev/tee0 takes the UUID in GP/RFC-4122 mixed-endian form: the first three
    // fields are byte-swapped by the driver before it prints the firmware name.
    // These bytes make the driver request "amdtee/773bd96f-b83f-4d52-b12dc529b13d8543.bin".
    unsigned char uuid[16] = {
        0x6f, 0xd9, 0x3b, 0x77, 0x3f, 0xb8, 0x52, 0x4d,
        0xb1, 0x2d, 0xc5, 0x29, 0xb1, 0x3d, 0x85, 0x43
    };
    if (argc > 2 && parse_uuid(argv[2], uuid) != 0) {
        fprintf(stderr, "bad uuid: %s\n", argv[2]);
        return 2;
    }

    unsigned char argbuf[sizeof(struct tee_ioctl_open_session_arg)];
    memset(argbuf, 0, sizeof(argbuf));
    struct tee_ioctl_open_session_arg *arg = (struct tee_ioctl_open_session_arg *)argbuf;
    memcpy(arg->uuid, uuid, 16);
    arg->clnt_login = TEE_IOCTL_LOGIN_PUBLIC;
    arg->num_params = 0;

    struct tee_ioctl_buf_data bd;
    bd.buf_ptr = (unsigned long)argbuf;
    bd.buf_len = sizeof(argbuf);

    int fd = open(dev, O_RDWR);
    if (fd < 0) { perror("open"); return 1; }

    errno = 0;
    int rc = ioctl(fd, TEE_IOC_OPEN_SESSION, &bd);
    printf("open_session: ioctl rc=%d errno=%d (%s)\n", rc, errno, strerror(errno));
    printf("  session=0x%x ret=0x%x ret_origin=0x%x\n", arg->session, arg->ret, arg->ret_origin);
    if (rc == 0 && arg->session)
        printf("  VERDICT: PSP ACCEPTED the TA (ret=0)\n");
    else
        printf("  VERDICT: session not opened (ret=0x%x)\n", arg->ret);
    close(fd);
    return 0;
}
