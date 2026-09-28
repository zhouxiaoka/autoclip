//! A non-inheritable job handle ties the entire backend tree to the desktop app.
use std::io;
use std::mem::{size_of, zeroed};
use std::os::windows::io::AsRawHandle;
use std::process::Child;
use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
use windows_sys::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
    SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
};

pub struct BackendJob(HANDLE);
// The owned kernel handle can be moved between threads; access is mutex protected.
unsafe impl Send for BackendJob {}

impl BackendJob {
    pub fn attach(child: &Child) -> io::Result<Self> {
        unsafe {
            let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if handle.is_null() {
                return Err(io::Error::last_os_error());
            }
            let job = Self(handle);
            let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                &limits as *const _ as *const _,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            ) == 0
                || AssignProcessToJobObject(handle, child.as_raw_handle()) == 0
            {
                return Err(io::Error::last_os_error());
            }
            Ok(job)
        }
    }
}

impl Drop for BackendJob {
    fn drop(&mut self) {
        unsafe {
            CloseHandle(self.0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufRead, BufReader, Write};
    use std::process::{Command, Stdio};
    use windows_sys::Win32::System::Threading::{
        OpenProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE,
    };

    #[test]
    fn dropping_job_terminates_parent_and_grandchild() {
        check_tree(false);
    }

    #[test]
    fn job_cleans_descendant_even_after_parent_exits() {
        check_tree(true);
    }

    fn check_tree(kill_parent_first: bool) {
        // Gate descendant creation until the parent has joined the job.
        let script = "import sys,subprocess,time; sys.stdin.readline(); p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)";
        let mut child = Command::new("python")
            .args(["-c", script])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let job = BackendJob::attach(&child).unwrap();
        child.stdin.take().unwrap().write_all(b"go\n").unwrap();
        let mut pid = String::new();
        BufReader::new(child.stdout.take().unwrap())
            .read_line(&mut pid)
            .unwrap();
        let descendant =
            unsafe { OpenProcess(PROCESS_SYNCHRONIZE, 0, pid.trim().parse().unwrap()) };
        assert!(!descendant.is_null());
        if kill_parent_first {
            child.kill().unwrap();
            child.wait().unwrap();
            assert_eq!(
                unsafe { WaitForSingleObject(descendant, 100) },
                258,
                "killing only the parent leaves the descendant alive"
            );
        }
        drop(job);
        let ended = unsafe { WaitForSingleObject(descendant, 5000) };
        unsafe {
            CloseHandle(descendant);
        }
        assert_eq!(ended, 0, "grandchild must exit when the job closes");
        assert_eq!(unsafe { WaitForSingleObject(child.as_raw_handle(), 5000) }, 0);
        child.wait().unwrap();
    }
}
