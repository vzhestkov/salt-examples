#!/usr/bin/perl

use strict;
use warnings;

use POSIX 'strftime';

my $IPC_SOCKET = "/var/run/salt/master/master_event_pub.ipc";
my $MASTER_LOG = "/var/log/salt/master";


sub get_pid_info {
    my $pid_info = {};
    my $pid;
    my $command;
    my $ps_fh;
    if ( open($ps_fh, "-|", "ps", "ax", "-o", "pid,command") ) {
        while ( my $l = <$ps_fh> ) {
            if ( ($pid, $command) = $l =~ /\A\s*(\d+)\s+(.*)/ ) {
                $pid_info->{$pid} = $command;
            }
        }
        close($ps_fh);
    }
    return $pid_info;
}

sub get_streams {
    my $master_ids = {};
    my $client_ids = {};
    my $pid_info = get_pid_info();
    my $ss_fh;
    my $local;
    my $peer;
    my $local_sid;
    my $peer_sid;
    my $pid;
    my $fd;
    if ( open($ss_fh, "-|", "ss", "-a", "--unix", "-p") ) {
        while ( my $l = <$ss_fh> ) {
            chomp($l);
            unless ( ($local, $local_sid, $peer, $peer_sid, $pid, $fd) = $l =~ /\Au_str\s+ESTAB\s+\d+\s+\d+\s+(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+.*,pid=(\d+),fd=(\d+).*/ ) {
                next;
            }
            if ( $local eq $IPC_SOCKET ) {
                $master_ids->{$peer_sid} = [$pid, $fd];
            } elsif ( $local eq "*" ) {
                $client_ids->{$local_sid} = [$pid, $fd];
            }
        }
        close($ss_fh);
    }
    my $streams = [];
    my $n = scalar(@{$streams});
    for $peer_sid ( keys(%{$master_ids}) ) {
        unless ( $n ) {
            my $pub_pid = $master_ids->{$peer_sid}[0];
            my $command = defined($pid_info->{$pub_pid}) ? $pid_info->{$pub_pid} : "N/D";
            $streams->[$n] = {"pid" => $pub_pid, "pub_pid" => $pub_pid, "fd" => "*", "command" => $command};
        }
        if ( defined($client_ids->{$peer_sid}) ) {
            $pid = $client_ids->{$peer_sid}[0];
            $fd = $master_ids->{$peer_sid}[1];
            my $command = defined($pid_info->{$pid}) ? $pid_info->{$pid} : "N/D";
            $n = scalar(@{$streams});
            $streams->[$n] = {"pid" => $pid, "pub_pid" => $master_ids->{$peer_sid}[0], "fd" => $fd, "command" => $command};
        }
    }
    return $streams;
}

sub report_subscribers {
    my ($fd) = @_;
    my $streams = get_streams();
    for my $stream (@{$streams}) {
        if ( !defined($fd) or $stream->{"fd"} == $fd ) {
            print(($stream->{"pid"} eq $stream->{"pub_pid"} ? " * " : "   ").$stream->{"pid"}.":".$stream->{"fd"}.":".$stream->{"command"}."\n");
        }
    }
}

print("[".strftime("%Y-%m-%d %T", localtime())."] Salt Master Event Publiser (*) subscribers:\n");
report_subscribers();
